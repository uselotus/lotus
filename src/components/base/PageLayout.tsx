import { Layout, PageHeader, PageHeaderProps } from "antd";
import React from "react";

export const PageLayout = ({ children, ...props }: PageHeaderProps) => {
  return (
    <div>
      <PageHeader
        {...props}
        title={<h1 className="text-3xl font-main ml-8">{props.title} </h1>}
      />
      <Layout.Content className="m-6 min-h-[calc(100vh-210px)]">
        {children}
      </Layout.Content>
    </div>
  );
};
