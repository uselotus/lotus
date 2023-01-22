import { Button as BTN } from "antd";

import "./button.less";

type Props = {
  level?: 1 | 2 | 3 | 4;
  children: any;
};
export const Button = ({ level = 1, children }: Props) => {
  return BTN;
};
