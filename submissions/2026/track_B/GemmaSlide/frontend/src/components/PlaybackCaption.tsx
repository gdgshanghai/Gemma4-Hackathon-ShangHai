import { Card, CardContent } from "@/components/ui/card";

interface PlaybackCaptionProps {
  segmentText: string;
  currentIndex: number;
  totalSegments: number;
}

export function PlaybackCaption({
  segmentText,
  currentIndex,
  totalSegments,
}: PlaybackCaptionProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm leading-6 text-foreground">{segmentText}</p>
        <p className="mt-2 text-xs font-medium text-muted-foreground">
          {currentIndex + 1}/{totalSegments}
        </p>
      </CardContent>
    </Card>
  );
}
