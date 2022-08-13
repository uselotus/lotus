import React, { FC, useState } from "react";
import { Table } from "antd";

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
    key: "plans",
    title: "Plans",
    dataIndex: "plans",
  },
];

interface Props {
  customerArray: {
    customer_id: string;
    name: string;
    plans: number;
  }[];
}

const ViewCustomers: FC<Props> = ({ customerArray }) => {
  const [data, setData] = useState(customerArray);
  return (
    <div>
      <div className="table">
        <Table dataSource={data} columns={columns} pagination={false} />
      </div>
    </div>
  );
};

export default ViewCustomers;
