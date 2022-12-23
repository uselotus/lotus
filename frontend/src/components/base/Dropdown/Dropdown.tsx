import React, { PropsWithChildren } from "react";
interface DropdownProps {
  className?: string;
}

const Dropdown = ({ children }: PropsWithChildren<DropdownProps>) => {
  return <div className="group relative inline-block">{children}</div>;
};

const Container: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
}) => {
  return (
    <>
      <div
        className={
          !className
            ? "absolute right-0 z-10 mt-2 hidden w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none group-hover:block"
            : [
                "absolute right-0 z-10 mt-2 hidden w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none group-hover-block",
                className,
              ].join(" ")
        }
        role="menu"
        aria-orientation="vertical"
        aria-labelledby="menu-button"
        tabIndex={-1}
      >
        <div className="py-1" role="none">
          {children}
        </div>
      </div>
    </>
  );
};

const MenuItem: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
}) => (
  <a
    href="#"
    className={
      !className
        ? "text-gray-700 block px-4 py-2 text-sm"
        : ["text-gray-700 block px-4 py-2 text-sm", className].join(" ")
    }
    role="menuitem"
    tabIndex={-1}
  >
    {children}
  </a>
);

const DropdownTrigger: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
}) => {
  return <div>{children}</div>;
};

Dropdown.Container = Container;
Dropdown.MenuItem = MenuItem;
Dropdown.Trigger = DropdownTrigger;

export default Dropdown;
