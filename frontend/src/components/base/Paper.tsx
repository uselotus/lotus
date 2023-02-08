import React, { PropsWithChildren } from "react";

type Props = {
  color?: "gold" | "default" | "white";
  border?: boolean;
  className?: string;
  children?: React.ReactNode | Element;
};
// eslint-disable-next-line import/prefer-default-export
export function Paper({
  border,
  color,
  className,
  children,
}: PropsWithChildren<Props>) {
  return (
    <div
      className={[
        "py-4 px-8 rounded-lg",
        color === "white" ? "bg-[#FFFFFF]" : "bg-[#FAFAFA]",
        className,
        border ? "border-2 border-solid border-[#EAEAEB]" : "",
      ].join(" ")}
    >
      {children}
    </div>
  );
}
