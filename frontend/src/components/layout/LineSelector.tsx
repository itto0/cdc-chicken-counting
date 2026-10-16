import { useId } from "react";
import { Layers } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface LineSelectorProps {
  className?: string;
  showLabel?: boolean;
}

export function LineSelector({ className, showLabel = true }: LineSelectorProps) {
  const { currentLineId, setLineId, lines } = useAppContext();
  const selectId = useId();

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {showLabel && (
        <label
          htmlFor={selectId}
          className="text-xs font-medium text-slate-500 flex items-center gap-1 whitespace-nowrap"
        >
          <Layers className="w-3.5 h-3.5 text-slate-400" />
          <span>Lini:</span>
        </label>
      )}
      <Select
        id={selectId}
        value={currentLineId}
        onChange={(e) => setLineId(e.target.value)}
        className="font-medium text-xs sm:text-sm h-8 py-0 min-w-[150px]"
      >
        {lines.map((line) => (
          <option key={line.id} value={line.id}>
            {line.name} {line.is_active ? "" : "(Nonaktif)"}
          </option>
        ))}
      </Select>
    </div>
  );
}
