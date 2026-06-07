import type React from "react";
import { Card, CardContent } from "@/components/ui/card";

interface TeleprompterProps {
  suggestion: string | null;
  loading: boolean;
}

const Teleprompter: React.FC<TeleprompterProps> = ({ suggestion, loading }) => (
  <Card>
    <CardContent className="p-4">
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        💡 AI 建议
      </p>
      <p className="text-lg leading-relaxed text-foreground">
        {loading ? (
          <span className="animate-pulse italic text-muted-foreground">
            AI 正在思考...
          </span>
        ) : suggestion ? (
          suggestion
        ) : (
          <span className="italic text-muted-foreground">
            开始讲话，AI 会给你提示...
          </span>
        )}
      </p>
    </CardContent>
  </Card>
);

export default Teleprompter;
