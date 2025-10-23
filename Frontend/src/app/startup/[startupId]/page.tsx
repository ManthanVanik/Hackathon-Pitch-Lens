
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import type { AnalysisData } from '@/lib/types';
import AnalysisDashboard from '@/components/analysis-dashboard';
import { Loader2 } from 'lucide-react';
import Header from '@/components/header';

const POLL_INTERVAL_MS = 5000;
const MAX_POLL_ATTEMPTS = 24;

const shouldContinuePolling = (data: AnalysisData | null) => {
  if (!data) {
    return false;
  }

  const statusValue = data.metadata?.status;
  const normalizedStatus =
    typeof statusValue === 'string' ? statusValue.toLowerCase() : undefined;
  const hasMemo = Boolean(data.memo?.draft_v1);
  const hasError = Boolean(data.metadata?.error);

  if (hasError || normalizedStatus === 'error') {
    return false;
  }

  if (normalizedStatus === 'processed' && hasMemo) {
    return false;
  }

  if (hasMemo) {
    return false;
  }

  return true;
};

export default function StartupPage({ params }: { params: { startupId: string } }) {
  const { startupId } = params;
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const pollAttemptsRef = useRef(0);

  const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? '').replace(/\/$/, '');
  const buildApiUrl = useCallback(
    (path: string) => `${apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`,
    [apiBaseUrl]
  );


  useEffect(() => {
    if (startupId === 'new') {
      setAnalysisData(null);
      setIsLoading(false);
      setIsPolling(false);
      setPollTimedOut(false);
      setError(null);
      return;
    }

    let isCancelled = false;
    let pollTimeout: ReturnType<typeof setTimeout> | null = null;

    const fetchAndMaybeSchedule = async (showSpinner: boolean) => {
      if (showSpinner) {
        setIsLoading(true);
      }

      try {
        setError(null);
        const response = await fetch(buildApiUrl(`/deals/${startupId}`), {
          cache: 'no-store',
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Analysis not found.');
          }
          throw new Error('Failed to fetch analysis data.');
        }

        const data = await response.json();

        if (isCancelled) {
          return;
        }

        setAnalysisData(data);

        if (shouldContinuePolling(data)) {
          if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
            setIsPolling(false);
            setPollTimedOut(true);
            return;
          }

          setIsPolling(true);
          pollAttemptsRef.current += 1;
          pollTimeout = setTimeout(() => {
            void fetchAndMaybeSchedule(false);
          }, POLL_INTERVAL_MS);
        } else {
          setIsPolling(false);
        }
      } catch (err: any) {
        if (isCancelled) {
          return;
        }
        setError(err.message || 'Failed to fetch analysis data.');
        setAnalysisData(null);
        setIsPolling(false);
      } finally {
        if (showSpinner && !isCancelled) {
          setIsLoading(false);
        }
      }
    };

    pollAttemptsRef.current = 0;
    setPollTimedOut(false);
    void fetchAndMaybeSchedule(true);

    return () => {
      isCancelled = true;
      if (pollTimeout) {
        clearTimeout(pollTimeout);
      }
    };
  }, [startupId, buildApiUrl]);


  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-8 md:py-12">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <Loader2 className="w-16 h-16 animate-spin text-primary mb-4" />
            <h2 className="text-2xl font-headline font-semibold text-primary">Loading Analysis...</h2>
            <p className="text-muted-foreground mt-2">Our AI is hard at work. This might take a moment.</p>
          </div>
        ) : error ? (
           <div className="text-center py-20">
              <h2 className="text-2xl font-headline font-semibold text-destructive">{error}</h2>
          </div>
        ) : analysisData ? (
          (() => {
            const statusValue = analysisData.metadata?.status;
            const normalizedStatus =
              typeof statusValue === 'string' ? statusValue.toLowerCase() : undefined;
            const hasMemo = Boolean(analysisData.memo?.draft_v1);
            const metadataError =
              typeof analysisData.metadata?.error === 'string'
                ? analysisData.metadata?.error
                : null;

            if (!hasMemo && isPolling) {
              return (
                <div className="flex flex-col items-center justify-center h-full text-center py-20">
                  <Loader2 className="w-14 h-14 animate-spin text-primary mb-4" />
                  <h2 className="text-2xl font-headline font-semibold text-primary">
                    We&apos;re still processing this startup
                  </h2>
                  <p className="text-muted-foreground mt-2">
                    This page will refresh automatically once the memo is ready.
                  </p>
                  {statusValue ? (
                    <p className="text-sm text-muted-foreground mt-4">Current status: {statusValue}</p>
                  ) : null}
                </div>
              );
            }

            if (metadataError || normalizedStatus === 'error') {
              return (
                <div className="text-center py-20">
                  <h2 className="text-2xl font-headline font-semibold text-destructive">
                    Analysis failed to complete
                  </h2>
                  <p className="text-muted-foreground mt-4">
                    {metadataError || 'Please try regenerating the summary once the underlying issue is resolved.'}
                  </p>
                </div>
              );
            }

            return (
              <>
                {!hasMemo && pollTimedOut ? (
                  <div className="mb-6 rounded-lg border border-dashed border-muted-foreground/40 bg-muted/40 p-4 text-sm text-muted-foreground">
                    We&apos;re still waiting for the memo to finish generating. The dashboard will update automatically when it&apos;s ready,
                    but you can also try generating the summary manually below.
                  </div>
                ) : null}
                <AnalysisDashboard analysisData={analysisData} startupId={startupId} />
              </>
            );
          })()
        ) : (
          <div className="text-center py-20">
              <h2 className="text-2xl font-headline font-semibold text-destructive">Analysis not found.</h2>
          </div>
        )}
      </main>
    </div>
  );
}
