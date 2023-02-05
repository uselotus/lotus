import { Typography } from "antd";
import React from "react";

import "./index.less";

type Props = {
  level?: 1 | 2 | 3 | 4;
  children: any;
};
export function Title({ level = 1, children }: Props) {
  return <Typography.Title level={level}>{children}</Typography.Title>;
}
