import React, { FC, useState, useEffect } from "react";
import {
  DownOutlined,
  EllipsisOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Table } from "antd";
import { CustomerTableItem } from "../types/customer-type";
import { Button, Tag, Tooltip } from "antd";
import { PlanDisplay } from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "./LoadingSpinner";
import SubscriptionStatistics from "./Dashboard/SubscriptionStatistics";

const columns: ProColumns<CustomerTableItem>[] = [
  {
    title: "Customer Id",
    width: 120,
    dataIndex: "customer_id",
    align: "left",
  },
  {
    title: "Name",
    width: 120,
    dataIndex: "customer_name",
    align: "left",
  },
  {
    title: "Plans",
    width: 120,
    dataIndex: "subscriptions",
    render: (_, record) => (
      <Tag color={"bruh"}>{record.subscriptions[0].billing_plan.name}</Tag>
    ),
  },
  {
    title: "Outstanding Revenue",
    width: 120,
    dataIndex: "total_revenue_due",
  },
];

interface Props {
  customerArray: CustomerTableItem[];
}

const CustomerTable: FC<Props> = ({ customerArray }) => {
  const navigate = useNavigate();

  const navigateCreateCustomer = () => {
    navigate("/customers/create");
  };

  return (
    <React.Fragment>
      <ProTable<CustomerTableItem>
        columns={columns}
        dataSource={customerArray}
        rowKey="customer_id"
        search={false}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
        }}
        options={false}
        toolBarRender={() => [
          <Button
            key="primary"
            type="primary"
            disabled={true}
            onClick={navigateCreateCustomer}
          >
            Create Customer
          </Button>,
        ]}
      />
    </React.Fragment>
  );
};

export default CustomerTable;
