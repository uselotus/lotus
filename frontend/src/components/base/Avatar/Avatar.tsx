import React from "react";

interface AvatarProps {
  src?: string;
  className?: string;
}
const Avatar: React.FC<AvatarProps> = ({ src, className = "" }) => (
  <div
    className={
      !className
        ? "z-10 block h-32 w-32 rounded-full cursor-pointer overflow-hidden  focus:outline-none focus:border-white"
        : [
            "z-10 block h-32 w-32 rounded-full cursor-pointer overflow-hidden  focus:outline-none focus:border-white",
            className,
          ].join(" ")
    }
  >
    {src ? (
      <img className="h-full w-full object-cover" src={src} alt="Your avatar" />
    ) : (
      <svg
        className="h-full w-full text-gray-300"
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )}
  </div>
);
export default Avatar;
