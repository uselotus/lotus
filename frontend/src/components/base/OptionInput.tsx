import React, { useState } from "react";
import { Select, FormInstance } from "antd";

interface Option {
  value: string;
  label: string;
}

export interface OptionInputProps {
  options?: Option[];
  name?: string;
  form?: FormInstance;
  placeholder?: string;
  style?: React.CSSProperties;
}

export default function OptionInput({
  options = [],
  name,
  form,
  placeholder,
  style,
}: OptionInputProps) {
  const [values, setValues] = useState<string[]>([]);

  const handleChange = (newValues: string[]) => {
    if (newValues.length === 0) {
      setValues([]);
      if (form && name) {
        form.setFieldValue(name, undefined);
      }
    } else {
      const newValue = newValues[newValues.length - 1];
      setValues([newValue]);
      if (form && name) {
        form.setFieldValue(name, newValue);
      }
    }
  };

  return (
    <Select
      placeholder={placeholder}
      value={values}
      mode="tags"
      onChange={handleChange}
      options={options}
      style={style!}
    />
  );
}
