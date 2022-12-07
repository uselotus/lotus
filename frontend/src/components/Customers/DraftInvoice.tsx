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

interface ExpandedDataType {
  key: React.Key;
  date: string;
  name: string;
  upgradeNum: string;
}

///generate dummy data for an invoice with many line items
const dummyInvoice: DraftInvoiceType = {
  invoice: {
    subscription: {
      start_date: "2021-01-01",
      end_date: "2021-01-01",
      status: "active",
    },
    pricing_unit: {
      code: "USD",
      symbol: "$",
      name: "US Dollar",
    },
    cost_due: 100,
    customer: {
      customer_id: "1",
      email: "dsfasfd@asdfsa.com",
      customer_name: "test",
    },
    line_items: [
      {
        name: "test",
        billing_type: "in_arrears",
        quantity: 1,
        subtotal: 100,
        plan_version_id: "1",
        start_date: "2021-01-01",
        end_date: "2021-01-01",
      },
    ],
  },
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

  const expandedRowRender = (record) => {
    console.log("record", record);
    const columns: TableColumnsType<LineItem> = [
      {
        title: "Item",
        dataIndex: "name",
        key: "name",
      },
      {
        title: "Quantity",
        dataIndex: "quantity",
        render: (_, record) => (
          <div className="flex flex-col">
            {record.quantity !== null ? record.quantity.toFixed(2) : "1"}
          </div>
        ),
      },
      {
        title: "Subtotal",
        dataIndex: "subtotal",
        render: (_, record) => (
          <div className="flex flex-col">
            {invoiceData?.invoice.currency.symbol}
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

  const organizedlineItems = useMemo(() => {
    if (invoiceData?.invoice && invoiceData?.invoice?.line_items) {
      const organizedItems: object = {};
      for (let i = 0; i < invoiceData.invoice.line_items.length; i++) {
        organizedItems[invoiceData.invoice.line_items[i].plan_version_id] =
          invoiceData.invoice.line_items[i];
      }
      return organizedItems;
    } else {
      return null;
    }
  }, [invoiceData]);

  //   const perPlanItems = useMemo(() => {
  //     if (
  //       invoiceData?.invoice &&
  //       invoiceData?.invoice?.line_items &&
  //       organizedlineItems
  //     ) {
  //         const planItems: object = {};

  //       for (let i = 0; i < organizedlineItems.ke; i++) {
  //         planItems[organizedlineItems[i].plan_name] = organizedlineItems[i];
  //       }

  //       return planItems;
  //     } else {
  //       return null;
  //     }
  //   }, [organizedlineItems]);

  return (
    <div>
      {invoiceData?.invoice !== null && invoiceData?.invoice !== undefined && (
        <div className="w-full space-y-8">
          <h2 className="mb-2 pb-4 pt-4 font-bold text-main">
            Draft Invoice View
          </h2>
          <div className="grid grid-cols-3">
            <p>
              <b>Issue Date: </b>
              {dayjs(invoiceData.invoice.subscription.end_date).format(
                "YYYY/MM/DD HH:mm"
              )}
            </p>
            <p>
              <b>Currency: </b> {invoiceData.invoice.currency.code}
            </p>
            <p>
              <b>Total Cost Due: </b>
              {invoiceData.invoice.currency.symbol}
              {invoiceData.invoice.cost_due}
            </p>
          </div>
          <Table
            dataSource={invoiceData.invoice.line_items}
            pagination={false}
            expandable={{ expandedRowRender }}
            columns={[
              {
                title: "Name",
                dataIndex: "name",
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
                title: "Subtotal",
                dataIndex: "subtotal",
                render: (_, record) => (
                  <div className="flex flex-col">
                    {invoiceData.invoice.currency.symbol}
                    {record.subtotal.toFixed(2)}
                  </div>
                ),
              },
            ]}
          />
        </div>
      )}
    </div>
  );
};

export default DraftInvoice;
