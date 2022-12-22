import React, { PropsWithChildren } from "react";
interface DropdownProps {
  className?: string;
}
const Dropdown = ({ children }: PropsWithChildren<DropdownProps>) => (
  <div>{children}</div>
);

const Container: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
}) => (
  <div
    className={
      !className
        ? "absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
        : [
            "absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none",
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
);

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
}) => <div>{children}</div>;

Dropdown.Container = Container;
Dropdown.MenuItem = MenuItem;
Dropdown.Trigger = DropdownTrigger;

export default Dropdown;
