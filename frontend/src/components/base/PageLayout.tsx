import { Layout, PageHeader, PageHeaderProps } from "antd";
// @ts-ignore
import React from "react";

export const PageLayout = ({ children, ...props }: PageHeaderProps) => {
  return (
    <div>
      <PageHeader title={<h1 className=" text-xl"></h1>} />
      <div className="mx-10 mt-10">
        <div className="flex items-center justify-between mb-6">
          {props.title ? (
            <h1 className="font-main">{props.title}</h1>
          ) : (
            <h1>{props.title}</h1>
          )}
          <div>{props.extra}</div>
        </div>
        <Layout.Content className="min-h-[calc(100vh-210px)]">
          {children}
        </Layout.Content>
      </div>
    </div>
  );
};
