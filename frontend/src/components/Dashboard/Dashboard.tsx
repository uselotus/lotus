import React, { FC } from "react";
import { Card, Col, Divider, PageHeader, Row } from "antd";
import RevenueDisplay from "./RevenueDisplay";
import SubscriptionStatistics from "./SubscriptionStatistics";
import MetricBarGraph from "./MetricBarGraph";
import dayjs from "dayjs";
import duration from "dayjs/plugin/duration";
import dayjsGenerateConfig from "rc-picker/lib/generate/dayjs";
import generatePicker from "antd/es/date-picker/generatePicker";
import { useQuery, UseQueryResult } from "react-query";
import { RevenueType } from "../../types/revenue-type";
import { GetRevenue } from "../../api/api";
import RevenueBarGraph from "./RevenueBarGraph";

import { PageLayout } from "../base/PageLayout";
import { CustomerByPlanPie } from "./CustomerByPlanPie";
import { toast } from "react-toastify";

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
          .subtract(dayjs.duration(dateRange[0].diff(dateRange[1])))
          .format("YYYY-MM-DD"),
        dateRange[1].subtract(1, "month").format("YYYY-MM-DD")
      ).then((res) => {
        return res;
      })
    );

  return (
    <PageLayout
      title={"Dashboard"}
      extra={[
        <RangePicker
          id="preset"
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
          <div className="grid grid-cols-12 justify-center align-baseline space-x-4">
            <div className="col-span-8">
              <RevenueDisplay
                total_revenue_1={data?.total_revenue_period_1}
                total_revenue_2={data?.total_revenue_period_2}
                isLoading={isLoading}
              />
            </div>
            <div className="col-span-4">
              <SubscriptionStatistics range={dateRange} />
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
