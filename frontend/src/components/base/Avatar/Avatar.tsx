import React from "react";

interface AvatarProps {
  src: string;
  className?: string;
}
const Avatar: React.FC<AvatarProps> = ({ src, className }) => (
  <div
    className={
      !className
        ? "z-10 block h-32 w-32 rounded-full cursor-pointer overflow-hidden border-2 border-gray-600 focus:outline-none focus:border-white"
        : [
            "z-10 block h-32 w-32 rounded-full cursor-pointer overflow-hidden border-2 border-gray-600 focus:outline-none focus:border-white",
            className,
          ].join(" ")
    }
  >
    <img className="h-full w-full object-cover" src={src} alt="Your avatar" />
  </div>
);
export default Avatar;
