import React from "react";

interface DividerProps {
  className?: string;
}
function Divider({ className }: DividerProps) {
  return <div
    className={`w-full h-[1.5px] mt-6 bg-card-divider ${
      className && className
    }`}
  />
}

export default Divider;
