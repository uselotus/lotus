// @ts-ignore
import React, { FC, useEffect } from "react";
import { Column } from "@ant-design/plots";
import { Select, Tag } from "antd";
// @ts-ignore
import dayjs from "dayjs";
import LoadingSpinner from "../LoadingSpinner";
import { useMutation } from "react-query";
import { Customer } from "../../api/api";
import { toast } from "react-toastify";
import CopyText from "../base/CopytoClipboard";

const CustomerInfoView: FC<any> = ({ data, cost_data, onDateChange }) => {
  const [transformedGraphData, setTransformedGraphData] = React.useState<any>(
    []
  );
  const [isEdit, setIsEdit] = React.useState(false);

  const updateCustomer = useMutation(
    (obj: { customer_id: string; default_currency_code: string }) =>
      Customer.updateCustomer(obj.customer_id, obj.default_currency_code),
    {
      onSuccess: () => {
        toast.success("Successfully Updated Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to Update Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

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
          metric: metric.metric.billable_metric_name,
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
    console.log(newgraphdata.flat(1));
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
    color: ["#C3986B", "#3F3F40"],

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
          Date Range :{"   "}
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
          <p>
            <b>Customer Name:</b> {data.customer_name ?? "N/A"}
          </p>
          <p>
            <b>Customer ID:</b> {<CopyText textToCopy={data.customer_id}/> ?? "N/A"}
          </p>
          <p>
            <b>Email:</b> {data.email ?? "N/A"}
          </p>
          <p>
            <b>Billing Address:</b> {data.billing_address ?? "N/A"}
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
            <b>Amount Due On Next Invoice:</b> {"$"}
            {data.next_amount_due.toFixed(2)}
          </p>
        </div>
        <div className="grid grid-cols-2 justify-items-center  gap-8 py-4 border-2 border-solid rounded border-[#EAEAEB]">
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
