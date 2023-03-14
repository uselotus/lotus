import React, { forwardRef, PropsWithChildren } from "react";

export type SelectRef = HTMLSelectElement;
interface SelectProps {
  className?: string;
  style?: React.CSSProperties;
  selected?: boolean;
  disabled?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
}
function Select({ children }: PropsWithChildren) {
  return <div>{children}</div>;
}
function SelectLabel({
  children,
  className,
}: PropsWithChildren<SelectProps>) {
  return <label
    className={
      !className
        ? "block text-sm font-medium text-gray-700"
        : ["block text-sm font-medium text-gray-700", className].join(" ")
    }
  >
    {children}
  </label>
}
const SelectElement = forwardRef<SelectRef, PropsWithChildren<SelectProps>>(
  ({ children, className = "", onChange, disabled }, ref) => (
    <select
      className={
        !className
          ? "mt-1 block w-2/5 rounded-md border-black border bg-white p-6 text-base  focus:outline-none  sm:text-sm"
          : [
              "mt-1 block w-2/5 rounded-md border-white bg-white p-6 text-base  focus:outline-none  sm:text-sm",
              className,
            ].join(" ")
      }
      disabled={disabled}
      ref={ref}
      onChange={(e) => onChange!(e)}
    >
      {children}
    </select>
  )
);

function SelectOption({ children, selected }: PropsWithChildren<SelectProps>) {
  return selected ? <option selected>{children}</option> : <option>{children}</option>
}

Select.Label = SelectLabel;
Select.Option = SelectOption;
Select.Select = SelectElement;

export default Select;
