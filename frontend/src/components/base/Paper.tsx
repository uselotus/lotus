import React from "react";

type Props = {
  color: "gold" | "white";
  border?: boolean;
  className?: string;
};
export const Paper = (props: Props) => {
  console.log(props.color, props.border, props.className);
  const className = props.className || "";
  return (
    <div
      {...props}
      className={[
        "py-4 px-8 rounded-lg",
        props.color === "white" ? "bg-[#FFFFFF]" : "bg-[#FAFAFA]",
        className,
        props.border ? "border-2 border-solid border-[#EAEAEB]" : "",
      ].join(" ")}
    />
  );
};

Paper.defaultProps = {
  color: "white",
  className: "",
};
