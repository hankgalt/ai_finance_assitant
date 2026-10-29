import { AlertCircle, CheckCircle2, Clock3, Info } from "lucide-react";

export function StateNotice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "success" | "warning" | "error";
  title: string;
  children?: React.ReactNode;
}) {
  const Icon = {
    info: Info,
    success: CheckCircle2,
    warning: Clock3,
    error: AlertCircle,
  }[tone];
  return (
    <div
      className={`state-notice state-${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon aria-hidden="true" size={19} />
      <div>
        <strong>{title}</strong>
        {children ? <div>{children}</div> : null}
      </div>
    </div>
  );
}
