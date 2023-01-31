import React, { FC } from "react";
import { useQuery } from "react-query";
import {
  DraftInvoiceType,
  ExternalLineItem,
  LineItem,
} from "../../types/invoice-type";
import { Invoices } from "../../api/api";
import { Table } from "antd";
import dayjs from "dayjs";
import type { TableColumnsType } from "antd";
import CustomerCard from "./Card/CustomerCard";
interface Props {
  customer_id: string;
}

const DraftInvoice: FC<Props> = ({ customer_id }) => {
  const { data: invoiceData, isLoading: invoiceLoading } =
    useQuery<DraftInvoiceType>(
      ["draft_invoice", customer_id],
      () => Invoices.getDraftInvoice(customer_id),
      {
        refetchInterval: 10000,
      }
    );

  const expandedRowRender = (invoice: ExternalLineItem) => (record) => {
    const columns: TableColumnsType<LineItem> = [
      {
        title: "ITEM",
        dataIndex: "name",
        key: "name",
      },
      {
        title: "DATES",
        dataIndex: "start_date",
        key: "date",
        render: (_, record) => {
          return (
            <div>
              {dayjs(record.start_date).format("MM/DD/YYYY") +
                " - " +
                dayjs(record.end_date).format("MM/DD/YYYY")}
            </div>
          );
        },
      },
      {
        title: "QUANTITY",
        dataIndex: "quantity",
        render: (_, record) => (
          <div className="flex flex-col">
            {record.quantity !== null ? record.quantity.toFixed(2) : ""}
          </div>
        ),
      },
      {
        title: "SUBTOTAL",
        dataIndex: "subtotal",
        render: (_, record) => (
          <div className="flex flex-col">
            {invoice.currency.symbol}
            {record.subtotal.toFixed(2)}
          </div>
        ),
      },
      {
        title: "BILLING TYPE",
        dataIndex: "billing_type",
      },
    ];

    return (
      <Table
        columns={columns}
        rowClassName="bg-card"
        dataSource={record.sub_items}
        pagination={false}
      />
    );
  };
  console.log(invoiceData?.invoices[0].line_items);
  return (
    <div>
      <h2 className="mb-2 mt-16 pb-4 pt-4 font-bold text-main">
        Draft Invoice View
      </h2>
      {invoiceData?.invoices !== null &&
        invoiceData?.invoices !== undefined &&
        invoiceData.invoices.map((invoice, index) => {
          return (
            <div
              key={index}
              className="grid gap-12 grid-cols-1  md:grid-cols-3"
            >
              <CustomerCard className="col-span-1">
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
                  dataSource={invoice.line_items}
                  pagination={false}
                  expandable={{ expandedRowRender: expandedRowRender(invoice) }}
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
                              {record.subscription_filters.map((filter) => {
                                return (
                                  <span key={filter.property_name}>
                                    {filter.property_name} : {filter.value}
                                  </span>
                                );
                              })}
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
          );
        })}
    </div>
  );
};

export default DraftInvoice;
