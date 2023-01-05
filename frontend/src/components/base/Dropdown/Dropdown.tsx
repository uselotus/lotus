import React, { PropsWithChildren, ReactElement, useEffect } from "react";
type TSelected = React.ReactNode | string;
interface DropdownProps {
  className?: string;
  onSelect?: (isOpen: boolean, selected: TSelected) => void;
}
interface DropdownContextState {
  isOpen: boolean;
  openHandler: VoidFunction;
  selected: React.ReactNode | string;
  closeHandler: (selected: TSelected) => void;
}
const DropdownContext = React.createContext({} as DropdownContextState);

const Dropdown = ({ children }: PropsWithChildren<DropdownProps>) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<TSelected>("");
  const openHandler = React.useCallback(() => setIsOpen(true), []);
  const closeHandler = React.useCallback(
    (selected: React.ReactNode | string) => {
      setSelected(selected);
      setIsOpen(false);
    },
    []
  );
  const value = React.useMemo(
    () => ({ isOpen, openHandler, closeHandler, selected }),
    [isOpen]
  );
  return (
    <div className="group relative inline-block">
      <DropdownContext.Provider value={value}>
        {children}
      </DropdownContext.Provider>
    </div>
  );
};
const useDropdownContext = () => {
  const context = React.useContext(DropdownContext);
  if (!context) {
    throw new Error(
      `Toggle compound components cannot be rendered outside the Toggle component`
    );
  }
  return context;
};
const Container: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
}) => {
  const { isOpen } = useDropdownContext();
  return (
    <>
      {isOpen && (
        <div
          className={
            !className
              ? "absolute right-0 z-10 mt-2  m-w-64 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none "
              : [
                  "absolute right-0 z-10 mt-2 m-w-64 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none",
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
      )}
    </>
  );
};

const MenuItem: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
  onSelect,
}) => {
  const { closeHandler, isOpen, selected } = useDropdownContext();

  return (
    <a
      href="#"
      className={
        !className
          ? "text-gray-700 block px-4 py-2 text-sm"
          : ["text-gray-700 block px-4 py-2 text-sm", className].join(" ")
      }
      role="menuitem"
      tabIndex={-1}
      onKeyDown={(e) => {
        let element = children as unknown as { type: string };
        if (element.type === "input" && e.key === "Enter") {
          onSelect && onSelect(isOpen, selected);
          closeHandler(children);
        }
      }}
      onClick={(e) => {
        e.preventDefault();
        let element = children as unknown as { type: string };
        if (element.type !== "input") {
          onSelect!(isOpen, selected);
          closeHandler(children);
        }
      }}
    >
      {children}
    </a>
  );
};

const DropdownTrigger: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
}) => {
  const { openHandler } = useDropdownContext();
  return <div onClick={openHandler}>{children}</div>;
};

Dropdown.Container = Container;
Dropdown.MenuItem = MenuItem;
Dropdown.Trigger = DropdownTrigger;

export default Dropdown;
