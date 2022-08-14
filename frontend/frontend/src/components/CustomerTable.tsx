import React, { FC, useState, useEffect } from "react";
import { Table } from "antd";
import { CustomerType } from "../types/customer-type";
const columns = [
  {
    key: "customer_id",
    title: "id",
    dataIndex: "customer_id",
  },
  {
    key: "name",
    title: "Name",
    dataIndex: "name",
  },
  {
    key: "balance",
    title: "Balance",
    dataIndex: "balance",
  },
];

interface Props {
  customerArray: CustomerType[];
}

const ViewCustomers: FC<Props> = ({ customerArray }) => {
  return (
    <div>
      <div className="table">
        <Table
          dataSource={customerArray}
          columns={columns}
          pagination={false}
        />
      </div>
    </div>
  );
};

export default ViewCustomers;
