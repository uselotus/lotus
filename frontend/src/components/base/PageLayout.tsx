import { Layout, PageHeader, PageHeaderProps } from "antd";
import React from "react";
import SlideOver from "../SlideOver/SlideOver";
import Heading from "./Heading/Heading";

interface PageLayoutProps extends PageHeaderProps {
  hasBackButton?: boolean;
  backButton?: React.ReactNode;
  aboveTitle?: boolean;
}
export const PageLayout = ({
  children,
  hasBackButton,
  backButton,
  aboveTitle = true,
  ...props
}: PageLayoutProps) => {
  return (
    <div>
      <SlideOver />

      <Heading
        hasBackButton={hasBackButton}
        aboveTitle={aboveTitle}
        backButton={backButton}
      />
      <PageHeader />

      <div className="mx-10 mt-16">
        <div className="flex items-center justify-between mb-6">
          {props.title ? (
            <h1 className={hasBackButton ? "font-main  mx-10" : "font-main"}>
              {hasBackButton && aboveTitle && backButton}
              <div className={hasBackButton ? "mt-12" : ""}>{props.title}</div>
            </h1>
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
