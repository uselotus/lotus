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
        props.color === "gold" ? "bg-[#CCA43B69]" : "bg-[#FAFAFA]",
        props.className,
      ].join(" ")}
    />
  );
};
