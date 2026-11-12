// A link to another app on the platform, drawn with that app's icon and an "opens elsewhere"
// arrow. It is a plain link, not a route: following it leaves this app, like opening another
// app on a phone.
import { ArrowUpRight } from "lucide-react";
import { APPS, type AppId } from "./apps";
import { cn } from "./ui";

export function AppLink({ app, className, iconOnly }: { app: AppId; className?: string; iconOnly?: boolean }) {
  const a = APPS[app];
  return (
    <a href={a.url} className={cn("tap flex items-center gap-3", className)} aria-label={`Open the ${a.name} app`} title={`Open ${a.name}`}>
      <img src={a.icon} alt="" className={iconOnly ? "h-7 w-7" : "h-[22px] w-[22px] shrink-0"} />
      {!iconOnly && (
        <>
          <span className="min-w-0 flex-1 truncate">{a.shortName}</span>
          <ArrowUpRight className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
        </>
      )}
    </a>
  );
}
