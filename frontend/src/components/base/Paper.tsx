import React from "react";

type Props = {
  color: "gold" | "default";
};
export const Paper = (props: Props | any) => {
  return (
    <div
      {...props}
      className={[
        "py-4 px-8 rounded-lg",
        props.color === "white" ? "bg-[#FFFFFF]" : "bg-[#FAFAFA]",
        props.className,
        props.border ? "border-2 border-solid border-[#EAEAEB]" : "",
      ].join(" ")}
    />
  );
};
