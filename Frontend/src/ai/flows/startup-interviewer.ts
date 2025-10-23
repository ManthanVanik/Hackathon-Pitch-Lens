import {z} from 'zod';
import type {
  AnalysisData,
  MemoV1,
  Founder,
  Financials,
  MarketAnalysis,
  BusinessModel,
} from '@/lib/types';

const ChatMessageSchema = z.object({
  role: z.enum(['user', 'model']),
  content: z.string(),
});

const StartupInterviewerInputSchema = z.object({
  analysisData: z.string().describe('The JSON string of the full startup analysis data.'),
  history: z.array(ChatMessageSchema).describe('The conversation history.'),
});
export type StartupInterviewerInput = z.infer<typeof StartupInterviewerInputSchema>;

const StartupInterviewerOutputSchema = z.object({
  message: z.string().describe("The chatbot's response."),
});
export type StartupInterviewerOutput = z.infer<typeof StartupInterviewerOutputSchema>;

const TOPIC_SEQUENCE = ['mission', 'market', 'product', 'goToMarket', 'financials', 'risk'] as const;

type TopicId = typeof TOPIC_SEQUENCE[number];

type SafeMemo = Partial<MemoV1> & {risk_metrics?: Partial<MemoV1['risk_metrics']>};

type ParsedAnalysis = {
  companyName?: string;
  productName?: string;
  sector?: string;
  memo?: SafeMemo;
  metadataFounders?: string[];
};

const emphasise = (value?: string | null): string | undefined => {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  return `**_${trimmed}_**`;
};

const toBullets = (...lines: Array<string | undefined>): string => {
  const bulletLines = lines
    .map(line => line?.trim())
    .filter((line): line is string => Boolean(line && line.length > 0))
    .map(line => (line.startsWith('•') ? `• ${line.slice(1).trim()}` : `• ${line}`));
  return bulletLines.slice(0, 4).join('\n');
};

function safeParseAnalysis(json: string): ParsedAnalysis {
  try {
    const parsed = JSON.parse(json) as Partial<AnalysisData>;
    return {
      companyName: parsed?.metadata?.company_name ?? parsed?.memo?.draft_v1?.company_overview?.name,
      productName: parsed?.metadata?.product_name ?? parsed?.memo?.draft_v1?.company_overview?.technology,
      sector: parsed?.metadata?.sector ?? parsed?.memo?.draft_v1?.company_overview?.sector,
      memo: parsed?.memo?.draft_v1 ?? (parsed?.memo as SafeMemo),
      metadataFounders: parsed?.metadata?.founder_names,
    };
  } catch (error) {
    console.warn('Failed to parse analysis JSON for chatbot', error);
    return {};
  }
}

function formatCompanyIntro(parsed: ParsedAnalysis): string {
  const parts: string[] = [];
  if (parsed.companyName) {
    parts.push(parsed.companyName);
  } else {
    parts.push('this startup');
  }
  if (parsed.productName && parsed.productName !== parsed.companyName) {
    parts.push(`(Product: ${parsed.productName})`);
  }
  if (parsed.sector) {
    parts.push(`in the ${parsed.sector} space`);
  }
  return parts.join(' ');
}

function cleanText(value?: string | null): string | undefined {
  if (!value) return undefined;
  return value.replace(/\s+/g, ' ').trim();
}

function formatList(values: string[], conjunction: 'and' | 'or' = 'and'): string {
  if (values.length === 0) {
    return '';
  }
  if (values.length === 1) {
    return values[0];
  }
  return `${values.slice(0, -1).join(', ')} ${conjunction} ${values[values.length - 1]}`;
}

function summariseFounders(memo?: SafeMemo, metadataFounders?: string[]): string | undefined {
  const founders: Founder[] = memo?.company_overview?.founders ?? [];
  if (founders.length > 0) {
    const details = founders.map(founder => {
      const pieces = [founder.name];
      const background = [cleanText(founder.professional_background), cleanText(founder.previous_ventures), cleanText(founder.education)]
        .filter(Boolean)
        .join('; ');
      if (background) {
        pieces.push(`(${background})`);
      }
      return pieces.join(' ');
    });
    return formatList(details);
  }
  if (metadataFounders && metadataFounders.length > 0) {
    return formatList(metadataFounders);
  }
  return undefined;
}

function summariseMarket(market?: MarketAnalysis): string | undefined {
  if (!market) return undefined;
  const tam = cleanText(market.industry_size_and_growth?.total_addressable_market?.value);
  const cagr = cleanText(market.industry_size_and_growth?.total_addressable_market?.cagr);
  const commentary = cleanText(market.industry_size_and_growth?.commentary);
  const parts = [];
  if (tam) {
    parts.push(`TAM around ${emphasise(tam) ?? tam}`);
  }
  if (cagr) {
    parts.push(`growth at ${emphasise(cagr) ?? cagr}`);
  }
  if (commentary) {
    parts.push(commentary);
  }
  return parts.join('. ');
}

function summariseFinancials(financials?: Financials): string | undefined {
  if (!financials) return undefined;
  const arr = cleanText(financials.srr_mrr?.current_booked_arr);
  const mrr = cleanText(financials.srr_mrr?.current_mrr);
  const burn = cleanText(financials.burn_and_runway?.implied_net_burn);
  const runway = cleanText(financials.burn_and_runway?.stated_runway);
  const valuation = cleanText(financials.valuation_rationale);
  const parts = [];
  if (arr) {
    parts.push(`Booked ARR: ${emphasise(arr) ?? arr}`);
  }
  if (mrr) {
    parts.push(`Current MRR: ${emphasise(mrr) ?? mrr}`);
  }
  if (burn || runway) {
    parts.push(`Runway plan: ${emphasise([burn, runway].filter(Boolean).join(', ')) ?? [burn, runway].filter(Boolean).join(', ')}`);
  }
  if (valuation) {
    parts.push(`Valuation rationale: ${valuation}`);
  }
  return parts.join('. ');
}

function summariseBusinessModel(model?: BusinessModel): string | undefined {
  if (!model) return undefined;
  const revenue = cleanText(model.revenue_streams);
  const pricing = cleanText(model.pricing);
  const scalability = cleanText(model.scalability);
  const ltv = cleanText(model.unit_economics?.customer_lifetime_value_ltv);
  const cac = cleanText(model.unit_economics?.customer_acquisition_cost_cac);
  const parts = [];
  if (revenue) {
    parts.push(`Revenue streams: ${revenue}`);
  }
  if (pricing) {
    parts.push(`Pricing: ${pricing}`);
  }
  if (scalability) {
    parts.push(`Scalability: ${scalability}`);
  }
  if (ltv || cac) {
    const unitEconomics = [ltv, cac].filter(Boolean).join(' vs ');
    parts.push(`Unit economics: ${emphasise(unitEconomics) ?? unitEconomics}`);
  }
  return parts.join('. ');
}

function summariseRisk(memo?: SafeMemo): string | undefined {
  const score = memo?.risk_metrics?.composite_risk_score;
  const interpretation = cleanText(memo?.risk_metrics?.score_interpretation);
  const narrative = cleanText(memo?.risk_metrics?.narrative_justification);
  const parts = [];
  if (typeof score === 'number') {
    parts.push(`Composite risk score ${emphasise(String(score)) ?? score}`);
  }
  if (interpretation) {
    parts.push(`Interpretation: ${interpretation}`);
  }
  if (narrative) {
    parts.push(narrative);
  }
  return parts.join('. ');
}

function buildMissionQuestion(parsed: ParsedAnalysis): string {
  const intro = formatCompanyIntro(parsed);
  const differentiator =
    cleanText(parsed.memo?.business_model?.scalability) ??
    cleanText(parsed.memo?.business_model?.revenue_streams);
  const focus = differentiator
    ? `The materials emphasise ${differentiator}.`
    : 'The materials outline mission and near-term milestones at a high level.';
  return `Mission & execution for ${intro}: ${focus} I can unpack those mission claims or pivot to another diligence lens—just say the word.`;
}

function buildMarketQuestion(parsed: ParsedAnalysis): string {
  const market = parsed.memo?.market_analysis?.industry_size_and_growth?.total_addressable_market?.value;
  const commentary = parsed.memo?.market_analysis?.industry_size_and_growth?.commentary;
  const intro = formatCompanyIntro(parsed);
  const detail = cleanText(market) ?? cleanText(commentary);
  const context = detail
    ? `Key market signal: ${detail}.`
    : 'The deck highlights a sizeable market but offers limited quant detail.';
  return `Market diligence on ${intro}: ${context} Let me know if you want a deeper breakdown or prefer to explore another area.`;
}

function buildProductQuestion(parsed: ParsedAnalysis): string {
  const intro = formatCompanyIntro(parsed);
  const differentiation =
    cleanText(parsed.memo?.business_model?.scalability) ??
    cleanText(parsed.memo?.business_model?.unit_economics?.customer_lifetime_value_ltv);
  const hook = differentiation
    ? `The deck leans on differentiation around ${differentiation}.`
    : 'The moat narrative is still developing.';
  return `Product moat for ${intro}: ${hook} I can summarise product defensibility signals or we can move to another diligence topic.`;
}

function buildGtmQuestion(parsed: ParsedAnalysis): string {
  const recentNews = parsed.memo?.market_analysis?.recent_news;
  const intro = formatCompanyIntro(parsed);
  const reference = cleanText(recentNews)
    ? `Recent activity notes: ${cleanText(recentNews)}.`
    : 'Pipeline commentary is included but light on specifics.';
  return `Go-to-market for ${intro}: ${reference} Happy to dive into channels, conversion, or expansion if that helps your diligence.`;
}

function buildFinancialQuestion(parsed: ParsedAnalysis): string {
  const burn = parsed.memo?.financials?.burn_and_runway?.implied_net_burn;
  const runway = parsed.memo?.financials?.burn_and_runway?.stated_runway;
  const intro = formatCompanyIntro(parsed);
  const tag = [cleanText(burn), cleanText(runway)].filter(Boolean).join(' and ');
  const framing = tag
    ? `Runway planning calls out ${tag}.`
    : 'Financial disclosures are directional but not exhaustive.';
  return `Financial outlook for ${intro}: ${framing} I can walk through revenue traction, burn, or projections—just let me know what matters most.`;
}

function buildRiskQuestion(parsed: ParsedAnalysis): string {
  const riskScore = parsed.memo?.risk_metrics?.composite_risk_score;
  const interpretation = parsed.memo?.risk_metrics?.score_interpretation;
  const intro = formatCompanyIntro(parsed);
  const baseline =
    typeof riskScore === 'number'
      ? `Composite risk score comes in around ${riskScore}.`
      : 'Risk commentary is fairly high level.';
  const followUp = cleanText(interpretation) ? `Interpretation: "${cleanText(interpretation)}."` : '';
  return `Risk signals for ${intro}: ${baseline} ${followUp} Call out if you want me to weigh the biggest flags or move to another angle.`;
}

const QUESTION_BUILDERS: Record<TopicId, (parsed: ParsedAnalysis) => string> = {
  mission: buildMissionQuestion,
  market: buildMarketQuestion,
  product: buildProductQuestion,
  goToMarket: buildGtmQuestion,
  financials: buildFinancialQuestion,
  risk: buildRiskQuestion,
};

type IntentHandler = {
  keywords: string[];
  handler: (parsed: ParsedAnalysis) => string | undefined;
};

const INTENT_HANDLERS: IntentHandler[] = [
  {
    keywords: ['founder', 'team', 'ceo', 'cto', 'people'],
    handler: parsed => {
      const foundersSummary = summariseFounders(parsed.memo, parsed.metadataFounders);
      if (!foundersSummary) return undefined;
      const intro = formatCompanyIntro(parsed);
      return toBullets(
        `Leadership for ${intro}`,
        `Key operators: ${foundersSummary}.`,
        'Flag any diligence points you want to explore next.'
      );
    },
  },
  {
    keywords: ['product', 'solution', 'technology', 'offering'],
    handler: parsed => {
      const name = formatCompanyIntro(parsed);
      const technology = cleanText(parsed.memo?.company_overview?.technology);
      const businessModel = summariseBusinessModel(parsed.memo?.business_model);
      return toBullets(
        `Product overview for ${name}: ${technology ?? 'focused solution for its core customers.'}`,
        businessModel ? `Model notes: ${businessModel}.` : undefined,
        'Need detail on roadmap, integrations, or IP? Happy to dive in.'
      );
    },
  },
  {
    keywords: ['market', 'tam', 'sam', 'customers', 'segment'],
    handler: parsed => {
      const intro = formatCompanyIntro(parsed);
      const market = summariseMarket(parsed.memo?.market_analysis);
      if (!market) {
        return toBullets(
          `${intro} is targeting a growing market.`,
          'The deck offered limited quant detail beyond directional commentary.',
          'Call out if you want me to surface competitor or customer references.'
        );
      }
      return toBullets(
        `${intro} is targeting this market:`,
        `${market}.`,
        'Want to scrutinise competitors, pricing power, or buyer persona next?'
      );
    },
  },
  {
    keywords: ['finance', 'financial', 'revenue', 'mrr', 'arr', 'runway', 'valuation', 'burn'],
    handler: parsed => {
      const financials = summariseFinancials(parsed.memo?.financials);
      if (!financials) {
        return toBullets(
          'Detailed financial tables were not present in the memo.',
          'Recommend requesting ARR, burn, and runway directly from the team.'
        );
      }
      return toBullets(
        'Financial profile highlights:',
        `${financials}.`,
        'Should we pressure test assumptions around runway, capital ask, or valuation next?'
      );
    },
  },
  {
    keywords: ['risk', 'safety', 'concern', 'challenge'],
    handler: parsed => {
      const risk = summariseRisk(parsed.memo);
      if (!risk) {
        return toBullets(
          'Risk summary not captured in the memo.',
          'Recommend reviewing original deck or requesting diligence responses.'
        );
      }
      return toBullets(
        'Risk lens from the memo:',
        `${risk}.`,
        'Highlight which mitigation area you want to stress-test.'
      );
    },
  },
  {
    keywords: ['mission', 'vision', 'goal', 'milestone'],
    handler: parsed => {
      const business = summariseBusinessModel(parsed.memo?.business_model);
      const intro = formatCompanyIntro(parsed);
      if (business) {
        return toBullets(
          `Mission focus for ${intro}:`,
          `${business}.`,
          'Want to align stated milestones with traction to date?'
        );
      }
      return toBullets(
        `Mission focus for ${intro}:`,
        'The deck offered only high-level mission language.',
        'Share which milestone matters and I will surface relevant context.'
      );
    },
  },
  {
    keywords: ['summary', 'overview', 'deal', 'company'],
    handler: parsed => {
      const intro = formatCompanyIntro(parsed);
      const founders = summariseFounders(parsed.memo, parsed.metadataFounders);
      const market = summariseMarket(parsed.memo?.market_analysis);
      const business = summariseBusinessModel(parsed.memo?.business_model);
      const financials = summariseFinancials(parsed.memo?.financials);
      return toBullets(
        `Snapshot: ${intro}.`,
        founders ? `Team: ${founders}.` : undefined,
        market ? `Market: ${market}.` : undefined,
        business ?? financials ?? 'Call out which diligence angle you want first.'
      );
    },
  },
];

function buildIntentResponse(question: string, parsed: ParsedAnalysis): string {
  const lower = question.toLowerCase();
  for (const {keywords, handler} of INTENT_HANDLERS) {
    if (keywords.some(keyword => lower.includes(keyword))) {
      const response = handler(parsed);
      if (response) {
        return response;
      }
    }
  }

  const intro = formatCompanyIntro(parsed);
  const business = summariseBusinessModel(parsed.memo?.business_model);
  const market = summariseMarket(parsed.memo?.market_analysis);
  const risk = summariseRisk(parsed.memo);
  return toBullets(
    `Snapshot: ${intro}.`,
    business ? `Model: ${business}.` : undefined,
    market ? `Market: ${market}.` : undefined,
    risk ?? 'Tell me which diligence lane you want to explore next.'
  );
}

function buildInitialGreeting(parsed: ParsedAnalysis): string {
  const intro = formatCompanyIntro(parsed);
  const founders = summariseFounders(parsed.memo, parsed.metadataFounders);
  const market = summariseMarket(parsed.memo?.market_analysis);
  return toBullets(
    `Review complete for ${intro}.`,
    founders ? `Team: ${founders}.` : undefined,
    market ? `Market signals: ${market}.` : undefined,
    'Choose a diligence focus—team, market, product, GTM, financials, or risk.'
  );
}

function runDeterministicFallback(parsedInput: StartupInterviewerInput): StartupInterviewerOutput {
  const parsedAnalysis = safeParseAnalysis(parsedInput.analysisData);
  const history = parsedInput.history;

  if (history.length === 0 || history[history.length - 1]?.role !== 'user') {
    const askedTopics = history
      .filter(message => message.role === 'model')
      .reduce((set, message) => {
        for (const topic of TOPIC_SEQUENCE) {
          if (message.content.toLowerCase().includes(topic)) {
            set.add(topic);
          }
        }
        return set;
      }, new Set<TopicId>());
    const nextTopic = ((): TopicId => {
      for (const topic of TOPIC_SEQUENCE) {
        if (!askedTopics.has(topic)) {
          return topic;
        }
      }
      return 'risk';
    })();
    const builder = QUESTION_BUILDERS[nextTopic] ?? buildMissionQuestion;
    const fallbackMessage = history.length === 0 ? buildInitialGreeting(parsedAnalysis) : builder(parsedAnalysis);
    return StartupInterviewerOutputSchema.parse({ message: fallbackMessage });
  }

  const lastUserMessage = history[history.length - 1];
  const deterministicResponse = buildIntentResponse(lastUserMessage.content, parsedAnalysis);
  return StartupInterviewerOutputSchema.parse({ message: deterministicResponse });
}

export async function interviewStartup(input: StartupInterviewerInput): Promise<StartupInterviewerOutput> {
  const parsedInput = StartupInterviewerInputSchema.parse(input);
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (apiBaseUrl) {
    try {
      const response = await fetch(`${apiBaseUrl}/chat/interview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analysisData: parsedInput.analysisData,
          history: parsedInput.history,
        }),
      });

      if (!response.ok) {
        throw new Error(`Chat API returned ${response.status}`);
      }

      const data = await response.json();
      return StartupInterviewerOutputSchema.parse(data);
    } catch (error) {
      console.error('Chat backend request failed, falling back to deterministic responses', error);
    }
  } else {
    console.warn('NEXT_PUBLIC_API_BASE_URL is not defined; chatbot will use deterministic fallback responses.');
  }

  return runDeterministicFallback(parsedInput);
}
