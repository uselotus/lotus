import { Table, Tag } from "antd";
import { FC, useState } from "react";
// @ts-ignore
import React from "react";
import {InvoiceType, MarkInvoiceStatusAsPaid} from "../../types/invoice-type";
// @ts-ignore
import dayjs from "dayjs";
import {useMutation} from "react-query";
import {Invoices} from "../../api/api";
import {toast} from "react-toastify";

interface Props {
  invoices: InvoiceType[] | undefined;
}

const CustomerInvoiceView: FC<Props> = ({ invoices }) => {
  const [invoiceVisible, setInvoiceVisible] = useState(false);
  const [invoiceState, setInvoiceState] = useState<InvoiceType>();

    const markInvoiceAsPaid = useMutation(
        (post: MarkInvoiceStatusAsPaid) => Invoices.markStatusAsPaid(post),
        {
            onSuccess: () => {
                toast.success("Successfully Changed Invoice Status to Paid", {
                    position: toast.POSITION.TOP_CENTER,
                });
            },
            onError: () => {
                toast.error("Failed to Changed Invoice Status to Paid", {
                    position: toast.POSITION.TOP_CENTER,
                });
            },
        }
    );

  const columns = [
    {
      title: "Invoice ID",
      dataIndex: "invoice_id",
      key: "invoice_id",
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
      render: (issue_date: string) => (
        <span>{dayjs(issue_date).format("YYYY/MM/DD HH:mm")}</span>
      ),
    },
    {
      title: "Status",
      dataIndex: "payment_status",
      key: "status",
      render: (_, record) => (
        <div className="flex">
            <Tag color={record.payment_status === "paid" ? "green" : "red"} key={record.payment_status}>
                {record.payment_status.toUpperCase()}
            </Tag>
            { record.payment_status === "unpaid" && (
                <Tag onClick={()=> {
                    console.log(record)
                    markInvoiceAsPaid.mutate( {
                        invoice_id: record.invoice_id,
                        status:"PAID",
                    })
                }} color="blue" key={record.invoice_id}>
                    Mark As Paid
                </Tag>
            )}
        </div>

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
