import { Button, Dropdown, Menu, Table, Tag, Tooltip } from "antd";
import { FC } from "react";
// @ts-ignore
import React from "react";
import {
  BalanceAdjustments,
  InvoiceType,
  MarkInvoiceStatusAsPaid,
} from "../../types/invoice-type";
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
  balanceAdjustments: BalanceAdjustments[];
}

const CustomerBalancedAdjustments: FC<Props> = ({ balanceAdjustments }) => {
  const columns = [
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      render: (amount: string) => <span>${parseFloat(amount).toFixed(2)}</span>,
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
    },
    {
      title: "Created On",
      dataIndex: "created",
      key: "created",
      render: (created: string) => (
        <span>{dayjs(created).format("YYYY/MM/DD HH:mm")}</span>
      ),
    },
    {
      title: "Effective At",
      dataIndex: "effective_at",
      key: "effective_at",
      render: (effective_at: string) => (
        <span>{dayjs(effective_at).format("YYYY/MM/DD HH:mm")}</span>
      ),
    },
    {
      title: "Expires At",
      dataIndex: "expires_at",
      key: "expires_at",
      render: (expires_at: string) => (
        <span>{dayjs(expires_at).format("YYYY/MM/DD HH:mm")}</span>
      ),
    },
  ];

  return (
    <div>
      <h2 className="mb-5">Credit Balance</h2>
      {!!balanceAdjustments?.length ? (
        <Table
          columns={columns}
          dataSource={balanceAdjustments}
          pagination={{ pageSize: 10 }}
        />
      ) : (
        <p>No Credit Items Found</p>
      )}
    </div>
  );
};

export default CustomerBalancedAdjustments;
