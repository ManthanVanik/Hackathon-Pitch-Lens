"use client";

import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import type { AnalysisData } from '@/lib/types';

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

type Props = {
  analysisData: AnalysisData;
  className?: string;
};

const coerce = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

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

export function ConnectFoundersButton({ analysisData, className }: Props) {
  const gmailLink = useMemo(() => {
    const rawPublic = analysisData.public_data as unknown;
    let publicData: Record<string, unknown> = {};
    if (rawPublic) {
      if (typeof rawPublic === 'string') {
        try {
          const parsed = JSON.parse(rawPublic);
          if (typeof parsed === 'object' && parsed !== null) {
            publicData = parsed as Record<string, unknown>;
          }
        } catch (error) {
          console.error('Failed to parse public_data payload for email CTA', error);
        }
      } else if (typeof rawPublic === 'object') {
        publicData = rawPublic as Record<string, unknown>;
      }
    }

    const namesMeta = (analysisData.metadata?.names ?? {}) as Partial<{
      company: string;
      product: string;
      display: string;
    }>;

    const companyName =
      coerce(namesMeta.company) ||
      coerce(analysisData.metadata?.company_legal_name) ||
      coerce(analysisData.metadata?.company_name) ||
      coerce(analysisData.memo?.draft_v1?.company_overview?.name);

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

    const founderEmails: string[] = [];
    const seen = new Set<string>();
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
      founderEmails.push(trimmed);
    };

    const metadata = analysisData.metadata as {
      founder_emails?: unknown;
      contact_email?: unknown;
      founder_contacts?: unknown;
    } | undefined;

    if (metadata) {
      collectEmails(metadata.founder_emails, push);
      collectEmails(metadata.contact_email, push);
      collectEmails(metadata.founder_contacts, push);
    }

    collectEmails(analysisData.memo?.draft_v1?.company_overview?.founders, push);
    collectEmails(analysisData.memo?.draft_v1, push);
    collectEmails(publicData, push);

    const fallbackCompany = companyName || displayName || productName || 'your company';
    const hasSpecificProduct = Boolean(productName);
    const mailSubject = hasSpecificProduct ? `Pitch Discussion - ${productName}` : 'Pitch Discussion';

    const mailBodyLines = hasSpecificProduct
      ? [
          'Hi,',
          '',
          `I'd love to schedule time to discuss about (${productName}) from your company (${fallbackCompany}).`,
          'Are you available for a 30-minute call this week to cover product traction, go-to-market, and financial plans?',
          '',
          'Looking forward to the conversation.',
          '',
          'Best regards,',
          '[Your Name]',
        ]
      : [
          'Hi,',
          '',
          "I'd love to schedule time to discuss further about your Pitch.",
          'Are you available for a 30-minute call this week to cover product traction, go-to-market, and financial plans?',
          '',
          'Looking forward to the conversation.',
          '',
          'Best regards,',
          '[Your Name]',
        ];

    const gmailParams = new URLSearchParams({
      view: 'cm',
      fs: '1',
      su: mailSubject,
      body: mailBodyLines.join('\n'),
    });

    if (founderEmails.length > 0) {
      gmailParams.set('to', founderEmails.join(','));
    }

    return `https://mail.google.com/mail/?${gmailParams.toString()}`;
  }, [analysisData]);

  return (
    <Button asChild variant="secondary" className={className}>
      <a href={gmailLink} target="_blank" rel="noopener noreferrer">
        Connect with founders
      </a>
    </Button>
  );
}
