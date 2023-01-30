import React, { FC, useEffect } from "react";
import { Column } from "@ant-design/plots";
import { useQueryClient, useMutation } from "react-query";

import { Select, Form, Typography } from "antd";
import { DraftInvoiceType } from "../../types/invoice-type";

import dayjs from "dayjs";
import { Customer } from "../../api/api";
import { toast } from "react-toastify";

import { CustomerType } from "../../types/customer-type";
import { CustomerCostType } from "../../types/revenue-type";
import { CurrencyType } from "../../types/pricing-unit-type";
import CustomerCard from "./Card/CustomerCard";
import { PencilSquareIcon } from "../base/PencilIcon";
import CopyText from "../base/CopytoClipboard";
import createShortenedText from "../../helpers/createShortenedText";
import useMediaQuery from "../../hooks/useWindowQuery";
import Divider from "../base/Divider/Divider";
import Badge from "../base/Badges/Badges";
interface CustomerInfoViewProps {
  data: CustomerType;
  cost_data: CustomerCostType;
  pricingUnits: CurrencyType[];
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
  const windowWidth = useMediaQuery();

  const [transformedGraphData, setTransformedGraphData] = React.useState<any>(
    []
  );
  const [form] = Form.useForm();
  const [currentCurrency, setCurrentCurrency] = React.useState<string>(
    data.default_currency.code ? data.default_currency.code : ""
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

  const invoiceData: DraftInvoiceType | undefined = queryClient.getQueryData([
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
        form.resetFields();
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
    let submittedAddress;
    if (
      city === "" &&
      line1 === "" &&
      country === "" &&
      postalCode === "" &&
      state === "" &&
      line2 === ""
    ) {
      submittedAddress = null;
    } else {
      submittedAddress = {
        city,
        line1,
        line2,
        country,
        postal_code: postalCode,
        state,
      };
    }
    const d = await updateCustomer.mutateAsync({
      customer_id: data.customer_id,
      address: submittedAddress,
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
      const result_list = day.cost_data.map((metric: any) => {
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
  }, [cost_data]);

  const onSwitch = (key: string) => {
    let start_date;
    const end_date = dayjs().format("YYYY-MM-DD");

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
    color: ["#33658A", "#C3986B", "#D9D9D9", "#171412", "#547AA5"],
  };

  return (
    <div className="flex flex-col">
      <div className="grid gap-12 grid-cols-1   md:grid-cols-3">
        <div className="col-span-2">
          <CustomerCard className="overflow-x-clip min-h-[210px]">
            <CustomerCard.Heading>
              <div className="flex">
                <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
                  Customer Details
                </Typography.Title>
                <div className="ml-auto">
                  <PencilSquareIcon />
                </div>
              </div>
              <Divider />
            </CustomerCard.Heading>
            {/* REMOVE THIS GAP WHEN YOU NO LONGER RENDER A MODAL */}
            <CustomerCard.Container className="grid gap-72  items-center grid-cols-1 md:grid-cols-[repeat(2,_minmax(0,_0.3fr))]">
              <CustomerCard.Block className="w-[256px] text-sm">
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Name
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">{data.customer_name}</div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
                    Add-On ID
                  </div>
                  <div className="flex gap-1 !text-card-grey font-menlo">
                    {" "}
                    <div>
                      {createShortenedText(
                        data.customer_id as string,
                        windowWidth >= 2500
                      )}
                    </div>
                    <CopyText
                      showIcon
                      onlyIcon
                      textToCopy={data.customer_id as string}
                    />
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Billing Address
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {data.address ? (
                        <div>
                          {data.address.line1},{data.address.state},
                          {data.address.country} {data.address.postal_code}
                        </div>
                      ) : (
                        "N/A"
                      )}
                    </div>
                  </div>
                </CustomerCard.Item>
              </CustomerCard.Block>
              <CustomerCard.Block className="w-[256px] text-sm">
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Email
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">{data.email}</div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
                    Default Currency
                  </div>
                  <div className="flex gap-1 !text-card-text Inter">
                    {" "}
                    <div>
                      {data.default_currency.code}-
                      {data.default_currency.symbol}
                    </div>
                  </div>
                </CustomerCard.Item>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Payment Method Provided
                  </div>
                  <div className="flex gap-1">
                    {" "}
                    <div className="Inter">
                      {data.payment_provider ? (
                        <div>{data.payment_provider}</div>
                      ) : (
                        "N/A"
                      )}
                    </div>
                  </div>
                </CustomerCard.Item>
              </CustomerCard.Block>
            </CustomerCard.Container>
          </CustomerCard>
        </div>
        <div className="col-span-1">
          <CustomerCard>
            <CustomerCard.Heading>
              <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
                Revenue Details
              </Typography.Title>
            </CustomerCard.Heading>
            <Divider />
            <CustomerCard.Container>
              <CustomerCard.Block>
                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Earned Revenue
                  </div>
                  <div className="Inter">
                    {data.default_currency.symbol}
                    {cost_data.total_revenue.toFixed(2)}
                  </div>
                </CustomerCard.Item>

                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Total Cost
                  </div>
                  <div className="Inter">
                    {data.default_currency.symbol}
                    {cost_data.total_cost.toFixed(2)}
                  </div>
                </CustomerCard.Item>

                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Profit Margin
                  </div>
                  <div
                    className={`Inter ${
                      cost_data.margin > 0
                        ? "text-emerald-800"
                        : "text-rose-700"
                    }`}
                  >
                    {cost_data.margin.toFixed(2)}%
                  </div>
                </CustomerCard.Item>

                <CustomerCard.Item>
                  <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
                    Next Invoice Due
                  </div>
                  <div className="Inter text-card-grey">
                    {data.default_currency.symbol}
                    {data.invoices[0].cost_due.toFixed(2)}
                  </div>
                </CustomerCard.Item>
              </CustomerCard.Block>
            </CustomerCard.Container>
          </CustomerCard>
        </div>
      </div>
      <div className="space-y-4 mt-8">
        <CustomerCard>
          <CustomerCard.Heading>
            <div className="flex">
              <Typography.Title className="pt-4 flex font-alliance !text-[18px]">
                Revenue vs Cost Per Day
              </Typography.Title>
              <div className="ml-auto">
                <div className="flex gap-4 items-center">
                  <div>
                    <Badge className="bg-transparent">
                      <Badge.Dot className="text-sky-800" />
                      <Badge.Content>Cost</Badge.Content>
                    </Badge>
                  </div>
                  <div>
                    <Badge className="bg-transparent">
                      <Badge.Dot className="text-darkgold" />
                      <Badge.Content>Revenue</Badge.Content>
                    </Badge>
                  </div>
                  <div className="">
                    {" "}
                    <Select defaultValue={"1"} onChange={onSwitch}>
                      <Select.Option value="1">Last 30 Days</Select.Option>
                      <Select.Option value="2">Last 60 Days</Select.Option>
                      <Select.Option value="3">This Month</Select.Option>
                      <Select.Option value="4">Year to date</Select.Option>
                    </Select>
                  </div>
                </div>
              </div>
            </div>
            <Divider />
          </CustomerCard.Heading>
          <CustomerCard.Container>
            <CustomerCard.Block>
              <Column {...config} />
            </CustomerCard.Block>
          </CustomerCard.Container>
        </CustomerCard>
      </div>
    </div>
  );
};

export default CustomerInfoView;
