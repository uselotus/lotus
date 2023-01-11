import React, { FunctionComponent, memo } from "react";

export type TooltipProps = {
  children: React.ReactNode | string;
  className?: string;
};

const Tooltip = ({ children }: TooltipProps) => {
  return <span className="group relative">{children}</span>;
};
const TooltipTop = ({ children, className }: TooltipProps) => (
  <span
    className={
      !className
        ? "pointer-events-none absolute bottom-20 left-1/2 -translate-x-1/2  rounded bg-white px-6 py-1 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100 "
        : [
            "pointer-events-none absolute  bottom-20 left-1/2 -translate-x-1/2 whitespace-pre-line rounded bg-white px-16 py-12 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100",
            className,
          ].join(" ")
    }
  >
    {children}
  </span>
);
const TooltipBottom = ({ children, className }: TooltipProps) => (
  <span
    className={
      !className
        ? "pointer-events-none absolute top-20 left-1/2 -translate-x-1/2  rounded bg-white  z-10 px-16 py-12 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2 before:border-4 before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100 text-sm"
        : [
            "pointer-events-none  absolute  w-full top-20 left-1/2 -translate-x-1/2  rounded bg-white z-10  px-16 py-12 text-black opacity-0 transition before:absolute before:left-1/2 before:top-full before:-translate-x-1/2  before:border-transparent before:border-t-black before:content-[''] group-hover:opacity-100 text-sm",
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
