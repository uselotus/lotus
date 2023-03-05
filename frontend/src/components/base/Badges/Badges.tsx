import React, { PropsWithChildren } from "react";

interface BadgeProps {
  className?: string;
  style?: React.CSSProperties;
  fill?: string;
  onClick?: VoidFunction;
}
const Badge = ({
  className = "",
  children,
  style,
  onClick,
}: PropsWithChildren<BadgeProps>) => {
  return (
    <span
      aria-hidden
      style={style}
      onClick={onClick}
      className={
        !className
          ? "flex items-center rounded-full bg-emerald-100 px-4 py-1 text-sm font-medium text-emerald-800"
          : [
              "flex items-center rounded-full  px-4 py-1 text-sm font-medium",
              className,
            ].join(" ")
      }
    >
      {children}
    </span>
  );
};

const BadgeDot = ({
  className = "",
  style,
  fill,
}: PropsWithChildren<BadgeProps>) => {
  return (
    <svg
      style={style}
      className={
        !className
          ? "-ml-1 mr-1.5 h-4 w-4 text-emerald-400"
          : ["-ml-1 mr-2 h-4 w-4", className].join(" ")
      }
      fill={fill || "currentColor"}
      viewBox="0 0 8 8"
    >
      <circle cx="4" cy="4" r="3" />
    </svg>
  );
};
function BadgeContent({ children }: PropsWithChildren) {
  return <>{children}</>;
}

Badge.Content = BadgeContent;
Badge.Dot = BadgeDot;
export default Badge;
