import React, { FC, Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "react-query";
import { DraftInvoiceType, LineItem } from "../../types/invoice-type";
import { Invoices } from "../../api/api";
import { Table } from "antd";
import dayjs from "dayjs";
import type { TableColumnsType } from "antd";

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

  const expandedRowRender = (invoice) => (record, index) => {
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
        dataSource={record.sub_items}
        pagination={false}
      />
    );
  };

  return (
    <div>
      <h2 className="mb-2 pb-4 pt-4 font-bold text-main">Draft Invoice View</h2>
      {invoiceData?.invoices !== null &&
        invoiceData?.invoices !== undefined &&
        invoiceData.invoices.map((invoice) => {
          return (
            <div className="w-full space-y-8">
              <div className="grid grid-cols-3">
                <p>
                  <b>Issue Date: </b>
                  {dayjs(invoice.issue_date).format("YYYY/MM/DD")}
                </p>
                <p>
                  <b>Currency: </b> {invoice.currency.name}
                </p>
                <p>
                  <b>Total Cost Due: </b>
                  {invoice.currency.symbol}
                  {invoice.cost_due.toFixed(2)}
                </p>
              </div>
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
                            {record.subscription_filters.map((filter: any) => {
                              return (
                                <span>
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
          );
        })}
    </div>
  );
};

export default DraftInvoice;
