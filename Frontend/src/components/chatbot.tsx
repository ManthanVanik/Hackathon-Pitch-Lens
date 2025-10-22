'use client';

import { useState, useEffect, useRef, useMemo, type ReactNode } from 'react';
import type { AnalysisData } from '@/lib/types';
import { interviewStartup, StartupInterviewerInput } from '@/ai/flows/startup-interviewer';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Send, User, Bot, Mail } from 'lucide-react';
import { ScrollArea } from './ui/scroll-area';

const EMAIL_REGEX = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;

const collectEmails = (value: unknown, push: (email: string) => void): void => {
  if (!value) {
    return;
  }

  if (typeof value === 'string') {
    const matches = value.match(EMAIL_REGEX);
    if (matches) {
      matches.forEach(match => {
        const trimmed = match.trim();
        if (trimmed) {
          push(trimmed);
        }
      });
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach(item => collectEmails(item, push));
    return;
  }

  if (typeof value === 'object') {
    Object.values(value as Record<string, unknown>).forEach(item => collectEmails(item, push));
  }
};

type Message = {
  role: 'user' | 'model';
  content: string;
};

export default function Chatbot({ analysisData }: { analysisData: AnalysisData }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const publicData = useMemo(() => {
    const raw = analysisData.public_data as unknown;
    if (!raw) return {} as Record<string, unknown>;
    if (typeof raw === 'string') {
      try {
        const parsed = JSON.parse(raw);
        return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
      } catch (error) {
        console.error('Failed to parse public_data payload for chatbot', error);
        return {} as Record<string, unknown>;
      }
    }
    if (typeof raw === 'object') {
      return raw as Record<string, unknown>;
    }
    return {} as Record<string, unknown>;
  }, [analysisData.public_data]);

  const namesMeta = (analysisData.metadata?.names ?? {}) as Partial<{
    company: string;
    product: string;
    display: string;
  }>;

  const coerce = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

  const companyName =
    coerce(namesMeta.company) ||
    coerce(analysisData.metadata?.company_legal_name) ||
    coerce(analysisData.metadata?.company_name) ||
    coerce(analysisData.memo?.draft_v1?.company_overview?.name);

  const sanitizeProductName = (value: string): string | undefined => {
    const trimmed = value.trim();
    if (!trimmed) {
      return undefined;
    }
    const normalized = trimmed.replace(/\s+/g, ' ');
    const wordCount = normalized.split(' ').length;
    if (normalized.length > 60 || wordCount > 6) {
      return undefined;
    }
    return normalized;
  };

  const rawProductName =
    coerce(namesMeta.product) ||
    coerce((analysisData.metadata as { product_name?: unknown } | undefined)?.product_name) ||
    '';

  const memoProductCandidate = coerce(analysisData.memo?.draft_v1?.company_overview?.technology);

  const productName =
    sanitizeProductName(rawProductName) ||
    (memoProductCandidate ? sanitizeProductName(memoProductCandidate) : undefined);

  const displayName =
    coerce(namesMeta.display) ||
    coerce(analysisData.metadata?.display_name) ||
    companyName ||
    productName ||
    'the company';

  const showProduct = Boolean(
    productName && (!companyName || productName.toLowerCase() !== companyName.toLowerCase())
  );
  const combinedName = showProduct ? `${companyName || displayName} (Product: ${productName})` : (companyName || displayName);

  const founderEmails = useMemo(() => {
    const seen = new Set<string>();
    const ordered: string[] = [];

    const push = (email: string) => {
      const trimmed = email.trim();
      if (!trimmed) {
        return;
      }
      const key = trimmed.toLowerCase();
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      ordered.push(trimmed);
    };

    const harvest = (value: unknown) => collectEmails(value, push);

    const metadata = analysisData.metadata as {
      founder_emails?: unknown;
      contact_email?: unknown;
      founder_contacts?: unknown;
    } | undefined;

    if (metadata) {
      harvest(metadata.founder_emails);
      harvest(metadata.contact_email);
      harvest(metadata.founder_contacts);
    }

    harvest(analysisData.memo?.draft_v1?.company_overview?.founders);
    harvest(analysisData.memo?.draft_v1);
    harvest(publicData);

    return ordered;
  }, [analysisData, publicData]);

  const mailSubject = `Intro call request – ${combinedName}`;
  const fallbackCompany = companyName || displayName || productName || 'your company';
  const productLabel = productName || 'your product';
  const companyLabel = fallbackCompany;
  const mailBody = [
    'Hi,',
    '',
    `I'd love to schedule time to discuss about (${productLabel}) from your company (${companyLabel}).`,
    'Are you available for a 30-minute call this week to cover product traction, go-to-market, and financial plans?',
    '',
    'Looking forward to the conversation.',
    '',
    'Best regards,',
    '[Your Name]',
  ].join('\n');

  const gmailParams = new URLSearchParams({
    view: 'cm',
    fs: '1',
    su: mailSubject,
    body: mailBody,
  });
  if (founderEmails.length > 0) {
    gmailParams.set('to', founderEmails.join(','));
  }
  const gmailLink = `https://mail.google.com/mail/?${gmailParams.toString()}`;

  const renderInlineSegments = (text: string, keyPrefix: string): ReactNode[] => {
    return text.split(/(\*\*_.+?_\*\*)/g).map((segment, idx) => {
      if (!segment) return null;
      if (segment.startsWith('**_') && segment.endsWith('_**')) {
        const content = segment.slice(3, -3);
        return (
          <span key={`${keyPrefix}-em-${idx}`} className="font-semibold italic text-foreground">
            {content}
          </span>
        );
      }
      return <span key={`${keyPrefix}-plain-${idx}`}>{segment}</span>;
    });
  };

  const renderMessageContent = (text: string, keyPrefix: string): ReactNode => {
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);
    if (lines.length === 0) {
      return <p key={`${keyPrefix}-empty`} className="text-sm leading-5">{text}</p>;
    }

    const nodes: ReactNode[] = [];
    let listBuffer: string[] = [];

    const flushList = () => {
      if (listBuffer.length === 0) return;
      nodes.push(
        <ul key={`${keyPrefix}-list-${nodes.length}`} className="list-disc space-y-1 pl-5 text-sm leading-5">
          {listBuffer.map((item, idx) => (
            <li key={`${keyPrefix}-item-${idx}`}>{renderInlineSegments(item, `${keyPrefix}-item-${idx}`)}</li>
          ))}
        </ul>
      );
      listBuffer = [];
    };

    lines.forEach((line, idx) => {
      if (line.startsWith('•')) {
        listBuffer.push(line.slice(1).trim());
        if (idx === lines.length - 1) {
          flushList();
        }
        return;
      }

      flushList();
      nodes.push(
        <p key={`${keyPrefix}-p-${nodes.length}`} className="text-sm leading-5">
          {renderInlineSegments(line, `${keyPrefix}-p-${idx}`)}
        </p>
      );
    });

    flushList();
    return <div className="space-y-2">{nodes}</div>;
  };

  const getInitialBotMessage = async () => {
    setIsLoading(true);
    try {
      const initialInput: StartupInterviewerInput = {
        analysisData: JSON.stringify(analysisData),
        history: [],
      };
      const result = await interviewStartup(initialInput);
      setMessages([{ role: 'model', content: result.message }]);
    } catch (e) {
      setMessages([{ role: 'model', content: 'Sorry, I am having trouble starting the conversation. Please try refreshing.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    getInitialBotMessage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisData]);

  useEffect(() => {
    if (scrollAreaRef.current) {
      // A hack to scroll to the bottom.
      const viewport = scrollAreaRef.current.querySelector('div[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input };
    const newMessages: Message[] = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      const result = await interviewStartup({
        analysisData: JSON.stringify(analysisData),
        history: newMessages,
      });
      setMessages((prevMessages) => [...prevMessages, { role: 'model', content: result.message }]);
    } catch (e) {
      setMessages((prevMessages) => [...prevMessages, { role: 'model', content: 'Sorry, something went wrong. Please try again.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="h-[70vh] flex flex-col">
      <CardHeader>
        <CardTitle className="font-headline text-2xl flex items-center gap-3"><Bot className="w-7 h-7 text-primary"/>AI Analyst Chat</CardTitle>
        <CardDescription>Ask diligence-focused questions to analyse the startup from an investor perspective.</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden">
        <ScrollArea className="flex-1 pr-4" ref={scrollAreaRef}>
          <div className="space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex items-start gap-3 ${message.role === 'user' ? 'justify-end' : ''}`}
              >
                {message.role === 'model' && (
                  <div className="bg-primary p-2 rounded-full text-primary-foreground">
                    <Bot size={20} />
                  </div>
                )}
                <div
                  className={`max-w-[75%] rounded-lg p-3 ${
                    message.role === 'user'
                      ? 'bg-secondary text-secondary-foreground'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {renderMessageContent(message.content, `message-${index}`)}
                </div>
                {message.role === 'user' && (
                    <div className="bg-accent p-2 rounded-full text-accent-foreground">
                        <User size={20} />
                    </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex items-start gap-3">
                <div className="bg-primary p-2 rounded-full text-primary-foreground">
                  <Bot size={20} />
                </div>
                <div className="bg-muted text-muted-foreground rounded-lg p-3 flex items-center space-x-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Thinking...</span>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
          <div className="flex flex-col gap-3 pt-4 border-t">
            <div className="flex items-center gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !isLoading && handleSendMessage()}
                placeholder="Type your question for the analyst..."
                disabled={isLoading}
              />
              <Button onClick={handleSendMessage} disabled={isLoading || !input.trim()}>
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <div className="flex justify-end">
              <Button asChild variant="secondary">
                <a href={gmailLink} target="_blank" rel="noopener noreferrer">
                  Connect with founders
                </a>
              </Button>
            </div>
          </div>
      </CardContent>
    </Card>
  );
}
