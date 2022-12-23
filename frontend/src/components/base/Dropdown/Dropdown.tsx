import React, { PropsWithChildren } from "react";
interface DropdownProps {
  className?: string;
}
interface DropdownContextState {
  isOpen: boolean;
  openHandler: VoidFunction;
  closeHandler: (selected: string) => void;
}
const DropdownContext = React.createContext({} as DropdownContextState);

const Dropdown = ({ children }: PropsWithChildren<DropdownProps>) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [selected, setSelected] = React.useState("");
  const openHandler = React.useCallback(() => setIsOpen(true), []);
  const closeHandler = React.useCallback((selected: string) => {
    setSelected(selected);
    setIsOpen(false);
  }, []);
  const value = React.useMemo(
    () => ({ isOpen, openHandler, closeHandler }),
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
      {!isOpen && (
        <div
          className={
            !className
              ? "absolute right-0 z-10 mt-2  w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none "
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
      )}
    </>
  );
};

const MenuItem: React.FC<PropsWithChildren<DropdownProps>> = ({
  children,
  className,
}) => {
  const { closeHandler } = useDropdownContext();
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
      onClick={() => closeHandler(children as string)}
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
