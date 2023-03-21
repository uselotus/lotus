import React from "react";
import { Select } from "antd";

interface SelectOption {
  label: string;
  value: string;
}

interface InputDropdownProps {
  options: SelectOption[];
  placeholder: string;
  value: string;
  setValue: (val: string) => void;
}

export default function InputDropdown({
  options,
  placeholder,
  value,
  setValue,
}: InputDropdownProps) {
  return (
    <Select
      value={value}
      mode="tags"
      placeholder={placeholder}
      options={options}
    />
  );
}
