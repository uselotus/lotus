import { Button, Dropdown, Menu, Table, Tag, Tooltip } from "antd";
import { FC } from "react";
// @ts-ignore
import React from "react";
import { InvoiceType, MarkInvoiceStatusAsPaid } from "../../types/invoice-type";
// @ts-ignore
import dayjs from "dayjs";
import { useMutation } from "react-query";
import { Invoices } from "../../api/api";
import { toast } from "react-toastify";
import { MoreOutlined } from "@ant-design/icons";
import { integrationsMap } from "../../types/payment-processor-type";

// @ts-ignore
const lotusUrl = new URL("./lotusIcon.svg", import.meta.url).href;

interface Props {
  invoices: InvoiceType[] | undefined;
}

const CustomerInvoiceView: FC<Props> = ({ invoices }) => {
  const changeStatus = useMutation(
    (post: MarkInvoiceStatusAsPaid) => Invoices.changeStatus(post),
    {
      onSuccess: (data) => {
        const status = data.payment_status.toUpperCase();
        toast.success(`Successfully Changed Invoice Status to ${status}`, {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to Changed Invoice Status", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const columns = [
    {
      title: "Source",
      dataIndex: "source",
      key: "source",
      render: (_, record) => (
        <div className="flex">
          {
            <Tooltip
              title={record.external_payment_obj_type ? "Stripe" : "Lotus"}
            >
              <img
                className="sourceIcon"
                src={
                  record.external_payment_obj_type
                    ? integrationsMap.stripe.icon
                    : lotusUrl
                }
                alt="Source icon"
              />
            </Tooltip>
          }
        </div>
      ),
    },
    {
      title: "Invoice #",
      dataIndex: "invoice_number",
      key: "invoice_number",
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
        <span>{dayjs(issue_date).format("YYYY/MM/DD")}</span>
      ),
    },
    {
      title: "Status",
      dataIndex: "payment_status",
      key: "status",
      render: (_, record) => (
        <div className="flex">
          <Tag
            color={record.payment_status === "paid" ? "green" : "red"}
            key={record.payment_status}
          >
            {record.payment_status.toUpperCase()}
          </Tag>
          {!record.external_payment_obj_type && (
            <div
              className="absolute right-3"
              onClick={(e) => e.stopPropagation()}
            >
              <Dropdown
                overlay={
                  <Menu>
                    <Menu.Item key="1">
                      <div className="archiveLabel">
                        Download Invoice Information
                      </div>
                    </Menu.Item>
                    <Menu.Item
                      key="2"
                      onClick={() => {
                        changeStatus.mutate({
                          invoice_number: record.invoice_number,
                          payment_status:
                            record.payment_status === "unpaid"
                              ? "paid"
                              : "unpaid",
                        });
                        record.payment_status =
                          record.payment_status === "unpaid"
                            ? "paid"
                            : "unpaid";
                      }}
                    >
                      <div className="archiveLabel">
                        {record.payment_status === "unpaid"
                          ? "Mark As Paid"
                          : "Mark As Unpaid"}
                      </div>
                    </Menu.Item>
                  </Menu>
                }
                trigger={["click"]}
              >
                <Button
                  type="text"
                  size="small"
                  onClick={(e) => e.preventDefault()}
                >
                  <MoreOutlined />
                </Button>
              </Dropdown>
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Invoices</h2>
      {invoices !== undefined ? (
        <Table
          columns={columns}
          dataSource={invoices}
          pagination={{
            showTotal: (total, range) => (
              <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
            ),
            pageSize: 6,
          }}
          showSorterTooltip={false}
        />
      ) : (
        <p>No invoices found</p>
      )}
    </div>
  );
};

export default CustomerInvoiceView;
