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

const columns: ProColumns<CustomerTableItem>[] = [
  {
    title: "id",
    width: 120,
    dataIndex: "customer_id",
    align: "left",
  },
  {
    title: "name",
    width: 120,
    dataIndex: "name",
    align: "left",
  },
  {
    title: "plan",
    width: 120,
    dataIndex: "plan.name",
    render: (_, record) => (
      <Tag color={record.plan.color}>{record.plan.name}</Tag>
    ),
  },
];

interface Props {
  customerArray: CustomerTableItem[];
}

const ViewCustomers: FC<Props> = ({ customerArray }) => {
  const navigate = useNavigate();

  const navigateCreateCustomer = () => {
    navigate("/customers/create");
  };
  return (
    <React.Fragment>
      <h1 className="text-3xl font-main">Customers</h1>

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

export default ViewCustomers;
