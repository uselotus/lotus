import { Table, Tag } from "antd";
import { FC, useState } from "react";
import React from "react";
import { InvoiceType } from "../../types/invoice-type";

interface Props {
  invoices: InvoiceType[] | undefined;
}

const CustomerInvoiceView: FC<Props> = ({ invoices }) => {
  const [invoiceVisible, setInvoiceVisible] = useState(false);
  const [invoiceState, setInvoiceState] = useState<InvoiceType>();

  const columns = [
    {
      title: "Invoice ID",
      dataIndex: "id",
      key: "id",
    },
    {
      title: "Amount",
      dataIndex: "cost_due",
      key: "cost_due",
      render: (cost_due: string) => (
        <span>${parseFloat(cost_due).toFixed(2)}</span>
      ),
    },
    {
      title: "Issue Date",
      dataIndex: "issue_date",
      key: "issue_date",
      render: (issue_date: string) => <span>{issue_date}</span>,
    },
    {
      title: "Status",
      dataIndex: "payment_status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "paid" ? "green" : "red"} key={status}>
          {status.toUpperCase()}
        </Tag>
      ),
    },
  ];

  return (
    <div>
      <h2 className="mb-5">Invoices</h2>
      {invoices !== undefined ? (
        <Table
          columns={columns}
          dataSource={invoices}
          pagination={{ pageSize: 10 }}
        />
      ) : (
        <p>No invoices found</p>
      )}
    </div>
  );
};

export default CustomerInvoiceView;
