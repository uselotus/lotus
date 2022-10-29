import {Layout, PageHeader, PageHeaderProps} from "antd";
// @ts-ignore
import React from "react";

export const PageLayout = ({children, ...props}: PageHeaderProps) => {
    return (
        <div>
            <PageHeader title={<h1 className="text-2xl">Welcome back, Test</h1>}/>
            <div className="flex items-center justify-between m-6">
                <div className='text-3xl font-bold'>{props.title}</div>
                <div>{props.extra}</div>
            </div>
            <Layout.Content className="m-6 min-h-[calc(100vh-210px)]">
                {children}
            </Layout.Content>
        </div>
    );
};
