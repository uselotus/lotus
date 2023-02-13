import React, { FC, useState } from "react";
import { useQuery } from "react-query";
import { Table } from "antd";
import dayjs from "dayjs";
import type { TableColumnsType } from "antd";
import { Invoices } from "../../api/api";
import {
  DraftInvoiceType,
  ExternalLineItem,
  LineItem,
} from "../../types/invoice-type";
import CustomerCard from "./Card/CustomerCard";

interface Props {
  customer_id: string;
}

const addKeysToLineItems = (lineItems: ExternalLineItem[]) => {
  return lineItems.map((lineItem, index) => {
    return { ...lineItem, key: index };
  });
};

const DraftInvoice: FC<Props> = ({ customer_id }) => {
  const { data: invoiceData, isLoading: invoiceLoading } =
    useQuery<DraftInvoiceType>(
      ["draft_invoice", customer_id],
      () => Invoices.getDraftInvoice(customer_id),
      {
        refetchInterval: 10000,
      }
    );
  const [expandedRowKey, setExpandedRowKey] = useState(null);

  const handleExpand = (expanded, record) => {
    if (expanded) {
      setExpandedRowKey(record.key);
    } else {
      setExpandedRowKey(null);
    }
  };

  const expandedRowRender = (invoice: ExternalLineItem) => {
    return (record) => {
      const columns: TableColumnsType<LineItem> = [
        {
          title: "Item",
          dataIndex: "name",
          key: "name",
        },
        {
          title: "Dates",
          dataIndex: "start_date",
          key: "date",
          render: (_, record) => (
            <div>
              {`${dayjs(record.start_date).format("MM/DD/YYYY")} - ${dayjs(
                record.end_date
              ).format("MM/DD/YYYY")}`}
            </div>
          ),
        },
        {
          title: "Quantity",
          dataIndex: "quantity",
          render: (_, record) => (
            <div className="flex flex-col">
              {record.quantity !== null ? record.quantity.toFixed(2) : ""}
            </div>
          ),
        },
        {
          title: "Subtotal",
          dataIndex: "subtotal",
          render: (_, record) => (
            <div className="flex flex-col">
              {invoice.currency.symbol}
              {record.subtotal.toFixed(2)}
            </div>
          ),
        },
        {
          title: "Billing Type",
          dataIndex: "billing_type",
        },
      ];

      return (
        <Table
          columns={columns}
          rowClassName="bg-card"
          dataSource={record.sub_items}
          pagination={false}
          onExpand={(expanded) => handleExpand(expanded, record)}
          expandedRowKeys={expandedRowKey === record.key ? [record.key] : []}
        />
      );
    };
  };

  return (
    <div>
      <h2 className="mb-2 mt-16 pb-4 pt-4  font-bold text-main">
        Draft Invoice View
      </h2>
      {invoiceData?.invoices !== null &&
        invoiceData?.invoices !== undefined &&
        invoiceData.invoices.map((invoice, index) => (
          <div key={index} className="grid gap-12 grid-cols-1  md:grid-cols-3">
            <CustomerCard className="col-span-1 h-[200px] shadow-none">
              <CustomerCard.Container>
                <CustomerCard.Block>
                  <CustomerCard.Item>
                    <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                      Issue Date
                    </div>
                    <div className="flex gap-1">
                      {" "}
                      <div className="Inter">
                        {" "}
                        {dayjs(invoice.issue_date).format("YYYY/MM/DD")}
                      </div>
                    </div>
                  </CustomerCard.Item>
                  <CustomerCard.Item>
                    <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                      Currency
                    </div>
                    <div className="flex gap-1">
                      {" "}
                      <div className="Inter"> {invoice.currency.name}</div>
                    </div>
                  </CustomerCard.Item>
                  <CustomerCard.Item>
                    <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                      Total Cost Due
                    </div>
                    <div className="flex gap-1">
                      {" "}
                      <div className="Inter">
                        {" "}
                        {invoice.currency.symbol}
                        {invoice.cost_due.toFixed(2)}
                      </div>
                    </div>
                  </CustomerCard.Item>
                </CustomerCard.Block>
              </CustomerCard.Container>
            </CustomerCard>
            <div className="col-span-2">
              <Table
                dataSource={addKeysToLineItems(invoice.line_items)}
                pagination={false}
                expandable={{
                  expandedRowRender: expandedRowRender(invoice),
                  onExpand: (expanded, record) =>
                    handleExpand(expanded, record),
                  expandedRowKeys: [expandedRowKey],
                }}
                columns={[
                  {
                    title: "Name",
                    dataIndex: "name",
                    key: "plan_name",
                    render: (_, record) => (
                      <div className="flex flex-col">
                        <p>{record.plan_name}</p>
                        {record.subscription_filters && (
                          <p>
                            {record.subscription_filters.map((filter) => (
                              <span key={filter.property_name}>
                                {filter.property_name} : {filter.value}
                              </span>
                            ))}
                          </p>
                        )}
                      </div>
                    ),
                  },
                  {
                    title: "Subtotal",
                    dataIndex: "subtotal",
                    render: (_, record) => (
                      <div className="flex flex-col">
                        {invoice.currency.symbol}
                        {record.subtotal.toFixed(2)}
                      </div>
                    ),
                  },
                ]}
              />
            </div>
          </div>
        ))}
    </div>
  );
};

export default DraftInvoice;
