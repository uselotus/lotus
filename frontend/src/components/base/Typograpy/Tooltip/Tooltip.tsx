import React, { FunctionComponent, memo } from "react";

export type TooltipProps = {
  children: React.ReactNode | string;
  className?: string;
};
interface ReactFC extends FunctionComponent<TooltipProps> {
  Top?: FunctionComponent<TooltipProps>;
  Bottom?: FunctionComponent<TooltipProps>;
}
const Tooltip: ReactFC = memo(({ children }) => {
  return <span className="group relative">{children}</span>;
});
const TooltipTop: React.FC<TooltipProps> = ({ children, className }) => (
  <span
    className={
      !className
        ? "pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-white px-2 py-1 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100"
        : [
            "pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-white px-2 py-1 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100",
            className,
          ].join(" ")
    }
  >
    {children}
  </span>
);
const TooltipBottom: React.FC<TooltipProps> = ({ children, className }) => (
  <span
    className={
      !className
        ? "pointer-events-none absolute bottom-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-white px-2 py-1 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100"
        : [
            "pointer-events-none absolute bottom-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-white px-2 py-1 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100",
            className,
          ].join(" ")
    }
  >
    {children}
  </span>
);

Tooltip.Top = TooltipTop;
Tooltip.Bottom = TooltipBottom;
Tooltip.displayName = "Tooltip";

export default Tooltip;
