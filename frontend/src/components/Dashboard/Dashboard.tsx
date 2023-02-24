import React, { FC, useRef } from "react";
import { Col, Row, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import duration from "dayjs/plugin/duration";
import dayjsGenerateConfig from "rc-picker/lib/generate/dayjs";
import generatePicker from "antd/es/date-picker/generatePicker";
import { useQuery, UseQueryResult } from "react-query";
import advancedFormat from "dayjs/plugin/advancedFormat";
import customParseFormat from "dayjs/plugin/customParseFormat";
import localeData from "dayjs/plugin/localeData";
import weekday from "dayjs/plugin/weekday";
import weekOfYear from "dayjs/plugin/weekOfYear";
import weekYear from "dayjs/plugin/weekYear";
import { Events, GetRevenue, GetSubscriptions } from "../../api/api";
import { RevenueType } from "../../types/revenue-type";
import MetricBarGraph from "./MetricBarGraph";
import { SubscriptionTotals } from "../../types/subscription-type";

import { PageLayout } from "../base/PageLayout";
import { CustomerByPlanPie } from "./CustomerByPlanPie";
import NumberDisplay from "./NumberDisplay";
import Select from "../base/Select/Select";
import MMRMovementChart from "./MRRMovementChart";
import MRRARRLineChart from "./MRRARRLineChart";
import LTVLineChart from "./LTVLineChart";

dayjs.extend(customParseFormat);
dayjs.extend(advancedFormat);
dayjs.extend(weekday);
dayjs.extend(localeData);
dayjs.extend(weekOfYear);
dayjs.extend(weekYear);

dayjs.extend(duration);

const DatePicker = generatePicker<dayjs.Dayjs>(dayjsGenerateConfig);
const { RangePicker } = DatePicker;

const dateFormat = "YYYY/MM/DD";
const defaultDate = [dayjs().subtract(1, "months").add(1, "day"), dayjs()];

const Dashboard: FC = () => {
  const [dateRange, setDateRange] = React.useState(defaultDate);
  const [selection, setSelection] = React.useState<
    "MRR Movement" | "Realized LTV per Customer" | "MRR / ARR"
  >("MRR Movement");
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  const selectRef = useRef<HTMLSelectElement | null>(null!);
  let selectedChart: React.ReactNode;
  const { data, isLoading }: UseQueryResult<RevenueType, RevenueType> =
    useQuery<RevenueType, RevenueType>(["total_revenue", dateRange], () =>
      GetRevenue.getMonthlyRevenue(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
        dateRange[0]
          .subtract(dayjs.duration(dateRange[1].diff(dateRange[0])))
          .format("YYYY-MM-DD"),
        dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => res)
    );

  const { data: subscriptionData, isLoading: subscriptionLoading } =
    useQuery<SubscriptionTotals>(["subscription_overview", dateRange], () =>
      GetSubscriptions.getSubscriptionOverview(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
        dateRange[0]
          .subtract(dayjs.duration(dateRange[1].diff(dateRange[0])))
          .format("YYYY-MM-DD"),
        dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => res)
    );

  const { data: eventData } = useQuery(["event_count", dateRange], () =>
    Events.getEventCount(
      dateRange[0].format("YYYY-MM-DD"),
      dateRange[1].format("YYYY-MM-DD"),
      dateRange[0]
        .subtract(dayjs.duration(dateRange[1].diff(dateRange[0])))
        .format("YYYY-MM-DD"),
      dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
    ).then((res) => res)
  );
  if (selection === "MRR Movement") {
    selectedChart = <MMRMovementChart />;
  } else if (selection === "MRR / ARR") {
    selectedChart = <MRRARRLineChart />;
  } else {
    selectedChart = <LTVLineChart />;
  }
  return (
    <PageLayout
      title="Dashboard"
      className="text-[24px]"
      extra={[
        <RangePicker
          id="preset"
          key="range-picker"
          format={dateFormat}
          ranges={{
            "This month": [dayjs().startOf("month"), dayjs().endOf("month")],
            "Last month": [
              dayjs().subtract(1, "months").startOf("month"),
              dayjs().subtract(1, "months").endOf("month"),
            ],
            "This year": [dayjs().startOf("year"), dayjs().endOf("year")],
            "All time": [dayjs().subtract(10, "years"), dayjs()],
          }}
          defaultValue={dateRange as [Dayjs, Dayjs]}
          onCalendarChange={(dates) => {
            setDateRange(dates as Dayjs[]);
          }}
        />,
      ]}
    >
      <Row gutter={[16, 16]}>
        <Col span="24">
          <div className="grid grid-cols-12 gap-18 justify-center align-baseline space-x-4">
            <div className="col-span-3">
              <NumberDisplay
                metric_1={data?.earned_revenue_period_1}
                metric_2={data?.earned_revenue_period_2}
                isLoading={isLoading}
                title="Earned Revenue"
                currency="USD"
              />
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={subscriptionData?.period_1_total_subscriptions}
                metric_2={subscriptionData?.period_2_total_subscriptions}
                isLoading={subscriptionLoading}
                title="Total Subscriptions"
              />
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={eventData?.total_events_period_1}
                metric_2={eventData?.total_events_period_2}
                isLoading={false}
                title="Events Tracked"
              />{" "}
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={subscriptionData?.period_1_new_subscriptions}
                metric_2={subscriptionData?.period_2_new_subscriptions}
                isLoading={subscriptionLoading}
                title="New Subscriptions"
              />{" "}
            </div>
          </div>
        </Col>
        <Col span="24">
          <div>
            <div className="flex mt-4">
              <Typography.Title className="pt-4 flex font-alliance">
                {selection}
              </Typography.Title>
              <span className="ml-auto">
                <Select>
                  <Select.Label className="">Billing Frequency</Select.Label>
                  <Select.Select
                    onChange={() => {
                      setSelection(
                        selectRef.current?.value as typeof selection
                      );
                    }}
                    className="!w-full !border !border-black"
                    ref={selectRef}
                  >
                    {/* <Select.Option selected>{selection}</Select.Option> */}
                    {[
                      "MRR Movement",
                      "Realized LTV per Customer",
                      "MRR / ARR",
                    ].map((el) => (
                      <Select.Option key={el}>{el}</Select.Option>
                    ))}
                  </Select.Select>
                </Select>
              </span>
            </div>

            {selectedChart}
          </div>
        </Col>
        <Col span="24">
          <div className="grid grid-cols-12 gap-18 justify-center space-x-4">
            <div className="col-span-8">
              <MetricBarGraph range={dateRange} />
            </div>
            <div className="col-span-4">
              <CustomerByPlanPie
                data={data?.daily_usage_revenue_period_1}
                isLoading={isLoading}
              />
            </div>
          </div>
        </Col>
      </Row>
    </PageLayout>
  );
};

export default Dashboard;
