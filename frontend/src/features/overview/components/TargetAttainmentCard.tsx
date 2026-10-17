import { Card, CardContent } from "@/components/ui/card";

interface TargetAttainmentCardProps {
  total: number;
  target: number;
  attainmentPct: number;
}

export function TargetAttainmentCard({
  total,
  target,
  attainmentPct,
}: TargetAttainmentCardProps) {
  const calculatedPct =
    typeof attainmentPct === "number" && !Number.isNaN(attainmentPct)
      ? attainmentPct
      : target > 0
        ? (total / target) * 100
        : 0;
  const displayPercentage = Math.round(calculatedPct);
  const percentage = Math.min(Math.max(displayPercentage, 0), 100);
  const targetFormatted = (target || 62000).toLocaleString("id-ID");

  // SVG circular gauge math
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm bg-white flex flex-col justify-between">
      <div className="p-5 pb-2">
        <h3 className="text-sm font-semibold text-slate-800">
          Capaian Target Harian
        </h3>
      </div>
      <CardContent className="p-5 pt-0 flex-1 flex flex-col justify-center">
        <div className="flex items-center gap-6">
          {/* Circular progress ring */}
          <div
            className="relative w-24 h-24 flex-shrink-0 flex items-center justify-center"
            role="progressbar"
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Capaian target harian"
          >
            <svg
              className="w-full h-full transform -rotate-90"
              viewBox="0 0 100 100"
              aria-hidden="true"
            >
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-slate-100"
                strokeWidth="9"
                stroke="currentColor"
                fill="transparent"
              />
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="text-blue-600 transition-all duration-700 ease-out"
                strokeWidth="9"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
              />
            </svg>
            <span className="absolute text-lg font-bold text-slate-800">
              {displayPercentage}%
            </span>
          </div>

          {/* Target achievement metrics & bar */}
          <div className="flex-1 min-w-0">
            {/* Horizontal progress bar */}
            <div
              className="w-full bg-slate-100 rounded-full h-2 overflow-hidden mb-3"
              role="progressbar"
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Progres capaian target"
            >
              <div
                className="bg-slate-800 h-2 rounded-full transition-all duration-500"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400">Daily goal Achievement</p>
            <p className="text-sm font-bold text-slate-800 mt-0.5">
              {targetFormatted} ekor
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
