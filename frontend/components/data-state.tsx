import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function LoadingBlocks({ rows = 3 }: { rows?: number }) {
  return (
    <div className="grid gap-3" aria-busy="true" aria-label="Loading content">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-20 w-full" />
      ))}
    </div>
  );
}

export function ErrorCard({
  title,
  message,
  onRetry,
  children,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 py-5">
        <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="text-section text-foreground">{title}</p>
          <p className="mt-1 text-caption text-muted-foreground">{message}</p>
          {(onRetry || children) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {onRetry && (
                <Button variant="outline" size="sm" onClick={onRetry}>
                  Retry
                </Button>
              )}
              {children}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
