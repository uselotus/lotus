import React, { useState } from "react";
import { Select, FormInstance } from "antd";

interface Option {
  value: string;
  label: string;
}

export interface OptionInputProps {
  options?: Option[];
  name: string;
  form: FormInstance;
}

export default function OptionInput({
  options = [],
  name,
  form,
}: OptionInputProps) {
  const [values, setValues] = useState<string[]>([]);

  const handleChange = (newValues: string[]) => {
    if (newValues.length === 0) {
      setValues([]);
      form.setFieldValue(name, undefined);
    } else {
      const newValue = newValues[newValues.length - 1];
      setValues([newValue]);
      form.setFieldValue(name, newValue);
    }
  };

  return (
    <Select
      id="event_name_input"
      value={values}
      mode="tags"
      onChange={handleChange}
      options={options}
    />
  );
}
