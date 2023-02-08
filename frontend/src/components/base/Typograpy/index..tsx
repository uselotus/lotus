/* eslint-disable react/require-default-props */
/* eslint-disable import/prefer-default-export */
import { Typography } from "antd";
import React, { PropsWithChildren } from "react";

import "./index.less";

type Props = {
  level?: 1 | 2 | 3 | 4;
};
export function Title({ level = 1, children }: PropsWithChildren<Props>) {
  return <Typography.Title level={level}>{children}</Typography.Title>;
}
