import React, { FC } from "react";
import { Col, Row } from "antd";
import MetricBarGraph from "./MetricBarGraph";
import dayjs from "dayjs";
import duration from "dayjs/plugin/duration";
import dayjsGenerateConfig from "rc-picker/lib/generate/dayjs";
import generatePicker from "antd/es/date-picker/generatePicker";
import { useQuery, UseQueryResult } from "react-query";
import { RevenueType } from "../../types/revenue-type";
import { Events, GetRevenue, GetSubscriptions } from "../../api/api";
import advancedFormat from "dayjs/plugin/advancedFormat";
import customParseFormat from "dayjs/plugin/customParseFormat";
import localeData from "dayjs/plugin/localeData";
import weekday from "dayjs/plugin/weekday";
import weekOfYear from "dayjs/plugin/weekOfYear";
import weekYear from "dayjs/plugin/weekYear";
import { SubscriptionTotals } from "../../types/subscription-type";

dayjs.extend(customParseFormat);
dayjs.extend(advancedFormat);
dayjs.extend(weekday);
dayjs.extend(localeData);
dayjs.extend(weekOfYear);
dayjs.extend(weekYear);

import { PageLayout } from "../base/PageLayout";
import { CustomerByPlanPie } from "./CustomerByPlanPie";
import NumberDisplay from "./NumberDisplay";

dayjs.extend(duration);

const DatePicker = generatePicker<dayjs.Dayjs>(dayjsGenerateConfig);
const { RangePicker } = DatePicker;

const dateFormat = "YYYY/MM/DD";
const defaultDate = [dayjs().subtract(1, "months").add(1, "day"), dayjs()];

const Dashboard: FC = () => {
  const [dateRange, setDateRange] = React.useState<any>(defaultDate);

  const { data, isLoading }: UseQueryResult<RevenueType, RevenueType> =
    useQuery<RevenueType, RevenueType>(["total_revenue", dateRange], () =>
      GetRevenue.getMonthlyRevenue(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
        dateRange[0]
          .subtract(dayjs.duration(dateRange[1].diff(dateRange[0])))
          .format("YYYY-MM-DD"),
        dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => {
        return res;
      })
    );

  const { data: subscriptionData, isLoading: subscriptionLoading } =
    useQuery<SubscriptionTotals>(["subscription_overview", dateRange], () =>
      GetSubscriptions.getSubscriptionOverview(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
        dateRange[0].subtract(1, "month").format("YYYY-MM-DD"),
        dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => {
        return res;
      })
    );

  const { data: eventData, isLoading: eventLoading } = useQuery(
    ["event_count"],
    () =>
      Events.getEventCount(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD")
      ).then((res) => {
        return res;
      })
  );

  return (
    <PageLayout
      title={"Dashboard"}
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
          defaultValue={dateRange}
          onCalendarChange={(dates) => {
            setDateRange(dates);
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
                title={"Earned Revenue"}
                currency={"USD"}
              />
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={subscriptionData?.period_1_total_subscriptions}
                metric_2={subscriptionData?.period_2_total_subscriptions}
                isLoading={subscriptionLoading}
                title={"Subscrptions"}
              />
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={eventData?.count_period_1 ?? 0}
                metric_2={eventData?.count_period_2 ?? 0}
                isLoading={false}
                title={"Events Tracked"}
              />{" "}
            </div>
            <div className="col-span-3">
              <NumberDisplay
                metric_1={subscriptionData?.period_1_new_subscriptions}
                metric_2={subscriptionData?.period_2_new_subscriptions}
                isLoading={subscriptionLoading}
                title={"New Subscriptions"}
              />{" "}
            </div>
          </div>
        </Col>
        <Col span="24">
          <div className="grid grid-cols-12 justify-center space-x-4">
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
