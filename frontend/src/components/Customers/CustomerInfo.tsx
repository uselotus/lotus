// @ts-ignore
import React, { FC, useEffect } from "react";
import { Column } from "@ant-design/plots";
import { useQueryClient } from "react-query";

import { Button, Select, Tag, Form, Input } from "antd";
import { DraftInvoiceType } from "../../types/invoice-type";

// @ts-ignore
import dayjs from "dayjs";
import LoadingSpinner from "../LoadingSpinner";
import { useMutation } from "react-query";
import { Customer } from "../../api/api";
import { toast } from "react-toastify";


import { CustomerType } from "../../types/customer-type";
import { CustomerCostType } from "../../types/revenue-type";
import { PricingUnit } from "../../types/pricing-unit-type";
interface CustomerInfoViewProps {
  data: CustomerType;
  cost_data: CustomerCostType;
  pricingUnits: PricingUnit[];
  onDateChange: (start_date: string, end_date: string) => void;
  refetch: VoidFunction;
}
const CustomerInfoView: FC<CustomerInfoViewProps> = ({
  data,
  cost_data,
  pricingUnits,
  onDateChange,
  refetch,
}) => {

  const [transformedGraphData, setTransformedGraphData] = React.useState<any>(
    []
  );
  const [form] = Form.useForm();
  const [currentCurrency, setCurrentCurrency] = React.useState<string>(
    data.default_currency.symbol
  );
  const [taxRate, setTaxRate] = React.useState(
    data.tax_rate ? data.tax_rate : 0
  );
  const [line1, setLine1] = React.useState(
    data.address ? data.address.line1 : ""
  );
  const [line2, setLine2] = React.useState(
    data.address && data.address.line2 ? data.address.line2 : ""
  );
  const [city, setCity] = React.useState(data.address ? data.address.city : "");
  const [state, setState] = React.useState(
    data.address ? data.address.state : ""
  );
  const [country, setCountry] = React.useState(
    data.address ? data.address.country : ""
  );
  const [postalCode, setPostalCode] = React.useState(
    data.address ? data.address.postal_code : ""
  );
  const [isEditing, setIsEditing] = React.useState(false);
  const queryClient = useQueryClient();

  let invoiceData: DraftInvoiceType | undefined = queryClient.getQueryData([
    "draft_invoice",
    data.customer_id,
  ]);

  const updateCustomer = useMutation(
    (obj: {
      customer_id: string;
      default_currency_code: string;
      address: CustomerType["address"];
      tax_rate: number;
    }) =>
      Customer.updateCustomer(
        obj.customer_id,
        obj.default_currency_code,
        obj.address,
        obj.tax_rate
      ),
    {
      onSuccess: () => {
        toast.success("Successfully Updated Customer Details", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to Update Customer Details", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );
  const makeEditable = () => {
    setIsEditing(true);
  };
  const EditCustomerHandler = async () => {
    const d = await updateCustomer.mutateAsync({
      customer_id: data.customer_id,
      address: {
        city,
        line1,
        line2,
        country,
        postal_code: postalCode,
        state,
      },
      default_currency_code: currentCurrency,
      tax_rate: taxRate,
    });

    refetch();
    setIsEditing(false);
  };
  const displayMetric = (metric: number | undefined): number => {
    if (metric === undefined) {
      return 0;
    }
    return metric;
  };
  useEffect(() => {
    const newgraphdata = cost_data.per_day.map((day: any) => {
      var result_list = day.cost_data.map((metric: any) => {
        return {
          date: day.date,
          amount: metric.cost,
          metric: metric.metric.metric_name,
          type: "cost",
        };
      });

      result_list.push({
        date: day.date,
        amount: day.revenue,
        type: "revenue",
        metric: "Revenue",
      });
      return result_list;
    });
    setTransformedGraphData(newgraphdata.flat(1));
  }, [cost_data]);

  const onSwitch = (key: string) => {
    var start_date;
    var end_date = dayjs().format("YYYY-MM-DD");

    switch (key) {
      case "1":
        start_date = dayjs().subtract(1, "month").format("YYYY-MM-DD");
        break;
      case "2":
        start_date = dayjs().subtract(2, "month").format("YYYY-MM-DD");
        break;
      case "3":
        start_date = dayjs().startOf("month").format("YYYY-MM-DD");
        break;
      case "4":
        start_date = dayjs().startOf("year").format("YYYY-MM-DD");
        break;
    }

    onDateChange(start_date, end_date);
  };

  const config = {
    data: transformedGraphData,
    xField: "date",
    yField: "amount",
    isGroup: true,
    isStack: true,
    seriesField: "metric",
    groupField: "type",
    colorField: "type", // or seriesField in some cases
    color: ["#C3986B", "#33658A", "#D9D9D9", "#171412", "#547AA5"],

    tooltip: {
      fields: ["type"],
    },
  };

  return (
    <div className="flex flex-col mb-8 ">
      <div className="grid grid-cols-2 items-center justify-between mb-2 pb-4 pt-4 ">
        <h2 className="pb-4 pt-4 font-bold text-main">Customer Details</h2>
        <div className="">
          {" "}
          Date Range :{"    "}
          <Select defaultValue={"1"} onChange={onSwitch}>
            <Select.Option value="1">Last 30 Days</Select.Option>
            <Select.Option value="2">Last 60 Days</Select.Option>
            <Select.Option value="3">This Month</Select.Option>
            <Select.Option value="4">Year to date</Select.Option>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8">
        <div className="border-2 border-solid rounded border-[#EAEAEB] py-4 px-8">
          {!isEditing && (
            <Button
              type="primary"
              size="large"
              className="w-1/3 mb-2"
              onClick={makeEditable}
            >
              Edit
            </Button>
          )}
          {!isEditing ? (
            <div>
              <p>
                <b>Customer Name:</b> {data.customer_name ?? "N/A"}
              </p>
              <p>
                <b>Customer ID:</b>{" "}
                {<span className="font-menlo">{data.customer_id}</span> ??
                  "N/A"}
              </p>
              <p>
                <b>Email:</b> {data.email ?? "N/A"}
              </p>
              <p>
                <b>Billing Address:</b>{" "}
                {data.address ? (
                  <div>
                    {data.address.line1},{data.address.state},
                    {data.address.country} {data.address.postal_code}
                  </div>
                ) : (
                  "N/A"
                )}
              </p>
              <p>
                <b>Default Currency:</b>{" "}
                {data ? (
                  <Tag>
                    {data.default_currency?.name +
                      " " +
                      data?.default_currency?.symbol}
                  </Tag>
                ) : (
                  "N/A"
                )}
                {/* {data.default_currency ? (
              <PricingUnitDropDown
                defaultValue={data.default_currency.code}
                setCurrentCurrency={(value) =>
                  updateCustomer.mutate({
                    customer_id: data.customer_id,
                    default_currency_code: value,
                  })
                }
              />
            ) : (
              "N/A"
            )} */}
              </p>
              <p>
                <b>Amount Due On Next Invoice:</b>{" "}
                {data?.default_currency?.symbol}
                {invoiceData?.invoices[0].cost_due.toFixed(2)}
              </p>
              <p>
                <b>Payment Method Connected:</b>{" "}
                {data.has_payment_method ? (
                  <Tag color="green">True</Tag>
                ) : (
                  <Tag color="red">False</Tag>
                )}
              </p>
              <p>
                <b>Tax Rate:</b> {data.tax_rate ?? "0"}%
              </p>
            </div>
          ) : (
            <Form form={form}>
              <Form.Item label="Customer Name" name="customer_name">
                <Input disabled={true} defaultValue={data.customer_name} />
              </Form.Item>
              <Form.Item
                label="Default Organization Currency"
                name="default_currency"
              >
                <Select
                  onChange={setCurrentCurrency}
                  defaultValue={currentCurrency}
                  options={pricingUnits?.map((pc) => {
                    return { label: `${pc.name} ${pc.symbol}`, value: pc.code };
                  })}
                />
              </Form.Item>
              <Form.Item label="Tax Rate" name="tax_rate">
                <Input
                  type="number"
                  step=".01"
                  max={999.9999}
                  onChange={(e) =>
                    setTaxRate(e.target.value as unknown as number)
                  }
                  defaultValue={data.tax_rate ?? 0}
                />
              </Form.Item>
              <Form.Item name="billing_address">
                <label className="mb-2">Billing Address: </label>
                <div className="flex gap-4 mt-2">
                  <Input
                    placeholder="Address Line 1"
                    defaultValue={line1}
                    onChange={(e) => setLine1(e.target.value)}
                    required
                  />
                  <Input
                    placeholder="Address Line 2"
                    defaultValue={line2}
                    onChange={(e) => setLine2(e.target.value)}
                  />
                </div>
                <div className="flex gap-4 mt-2">
                  <Input
                    placeholder="City"
                    onChange={(e) => setCity(e.target.value)}
                    defaultValue={city}
                    required
                  />
                  <Input
                    placeholder="Country"
                    defaultValue={country}
                    onChange={(e) => setCountry(e.target.value)}
                    required
                  />
                </div>
                <div className="flex gap-4 mt-2">
                  <Input
                    placeholder="State"
                    defaultValue={state}
                    onChange={(e) => setState(e.target.value)}
                    required
                  />
                  <Input
                    defaultValue={postalCode}
                    placeholder="Zip Code"
                    onChange={(e) => setPostalCode(e.target.value)}
                    required
                  />
                </div>
              </Form.Item>
              <div className="flex gap-2 mb-2">
                <Button
                  type="primary"
                  size="large"
                  className=" w-full"
                  onClick={EditCustomerHandler}
                >
                  Submit
                </Button>
                <Button
                  type="ghost"
                  size="large"
                  className=" w-full"
                  onClick={() => setIsEditing(false)}
                >
                  Cancel
                </Button>
              </div>
            </Form>
          )}
        </div>
        <div className="grid grid-cols-3 place-items-center gap-8 py-4">
          <div>
            <p className=" mb-4">Earned Revenue</p>
            {cost_data === undefined ? (
              <LoadingSpinner />
            ) : (
              <span className="text-3xl font-bold">
                {new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                }).format(displayMetric(cost_data.total_revenue))}
              </span>
            )}
          </div>

          <div>
            <p className=" mb-4">Total Cost</p>
            {cost_data === undefined ? (
              <LoadingSpinner />
            ) : (
              <span className="text-3xl font-bold">
                {new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                }).format(displayMetric(cost_data.total_cost))}
              </span>
            )}
          </div>
          <div className="">
            <p className=" mb-4">Profit Margin</p>
            {cost_data.margin === undefined ? (
              <LoadingSpinner />
            ) : cost_data.margin < 0 ? (
              <span className="text-3xl font-bold text-danger">
                {displayMetric(cost_data.margin * 100).toFixed(2)}%
              </span>
            ) : (
              <span className="text-3xl font-bold text-success">
                {displayMetric(cost_data.margin * 100).toFixed(2)}%
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="space-y-4 mt-8">
        <div className="flex items-center space-x-8">
          <h2 className="mb-2 pb-4 pt-4 font-bold text-main">
            Revenue vs Cost Per Day
          </h2>
        </div>
        <Column {...config} />
      </div>
    </div>
  );
};

export default CustomerInfoView;
