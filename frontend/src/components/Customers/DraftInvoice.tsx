import React, { FC, Fragment, useEffect, useMemo, useState } from "react";
import { useQuery } from "react-query";
import { DraftInvoiceType } from "../../types/invoice-type";
import { Invoices } from "../../api/api";
import { Table } from "antd";
import dayjs from "dayjs";

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
              <b>Currency: </b> {invoiceData.invoice.pricing_unit.code}
            </p>
            <p>
              <b>Total Cost Due: </b>
              {invoiceData.invoice.pricing_unit.symbol}
              {invoiceData.invoice.cost_due}
            </p>
          </div>
          <Table
            dataSource={invoiceData.invoice.line_items}
            pagination={false}
            columns={[
              {
                title: "Name",
                dataIndex: "name",
                render: (_, record) => (
                  <div className="flex flex-col">
                    <p>{record.name}</p>
                    {record.metadata && (
                      <p className="text-s text-grey2">
                        {Object.keys(record.metadata).map((key) => (
                          <span>
                            {key}: {record.metadata[key]}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                ),
              },
              {
                title: "Quantity",
                dataIndex: "quantity",
                render: (_, record) => (
                  <div className="flex flex-col">
                    {record.quantity !== null && record.quantity.toFixed(2)}
                  </div>
                ),
              },
              {
                title: "Subtotal",
                dataIndex: "subtotal",
                render: (_, record) => (
                  <div className="flex flex-col">
                    {invoiceData.invoice.pricing_unit.symbol}
                    {record.subtotal.toFixed(2)}
                  </div>
                ),
              },
              {
                title: "Billing Type",
                dataIndex: "billing_type",
              },
            ]}
          />
        </div>
      )}
    </div>
  );
};

export default DraftInvoice;
