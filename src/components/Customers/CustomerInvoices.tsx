import { Table, Tag } from "antd";

interface Props {
    invoices:
}

const CustomerInvoiceView: FC<Props> = ({ invoices }) => {
  const [invoiceVisible, setInvoiceVisible] = useState(false);
  const [invoiceState, setInvoiceState] = useState<InvoiceState>({
    title: "Create an Invoice",
    customer_id: "",
    invoice_id: "",
    amount: 0,
    due_date: "",
    status: "unpaid",
    subscription_uid: "",
  });

  const columns = [
    {
      title: "Invoice ID",
      dataIndex: "invoice_id",
      key: "invoice_id",
    },
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      render: (amount: number) => <span>${amount}</span>,
    },
    {
      title: "Due Date",
      dataIndex: "due_date",
      key: "due_date",
      render: (due_date: string) => <span>{due_date}</span>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "paid" ? "green" : "red"} key={status}>
          {status.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "Subscription UID",
      dataIndex: "subscription_uid",
      key: "subscription_uid",
      render: (subscription_uid: string) => (
        <span>{subscription_uid.substring(0, 10)}...</span>
      ),
    },
  ];

  return (
    <div>
      <Table
        columns={columns}
        dataSource={tableData}
        pagination={{ pageSize: 10 }}
      />
    </div>
  );
};

export default CustomerInvoiceView;
