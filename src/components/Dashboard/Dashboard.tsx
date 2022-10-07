import React, { FC } from "react";
import { Card, Col, Divider, PageHeader, Row } from "antd";
import RevenueDisplay from "./RevenueDisplay";
import SubscriptionStatistics from "./SubscriptionStatistics";
import MetricBarGraph from "./MetricBarGraph";
import dayjs, { Dayjs } from "dayjs";
import dayjsGenerateConfig from "rc-picker/lib/generate/dayjs";
import generatePicker from "antd/es/date-picker/generatePicker";
import { useQuery, UseQueryResult } from "react-query";
import { RevenueType } from "../../types/revenue-type";
import { GetRevenue } from "../../api/api";
import RevenueBarGraph from "./RevenueBarGraph";

import { Content } from "antd/lib/layout/layout";
import { PageLayout } from "../base/PageLayout";

const DatePicker = generatePicker<Dayjs>(dayjsGenerateConfig);
const { RangePicker } = DatePicker;

const dateFormat = "YYYY/MM/DD";
const defaultDate = [dayjs().subtract(1, "months"), dayjs()];

const Dashboard: FC = () => {
  const [dateRange, setDateRange] = React.useState<any>(defaultDate);

  const { data, isLoading }: UseQueryResult<RevenueType, RevenueType> =
    useQuery<RevenueType, RevenueType>(["total_revenue", dateRange], () =>
      GetRevenue.getMonthlyRevenue(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
        dateRange[0].subtract(1, "month").format("YYYY-MM-DD"),
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
          bordered={false}
          format={dateFormat}
          defaultValue={dateRange}
          onCalendarChange={(dates) => {
            setDateRange(dates);
          }}
        />,
      ]}
    >
      <Row>
        <Col span="24">
          <div className="grid grid-cols-2 justify-center ">
            <Card className="max-w-lg">
              <RevenueDisplay
                total_revenue_1={data?.total_revenue_period_1}
                total_revenue_2={data?.total_revenue_period_2}
                isLoading={isLoading}
              />
            </Card>
            <Card className="max-w-lg">
              <SubscriptionStatistics range={dateRange} />
            </Card>
          </div>
          <Divider />
          <div className="my-10">
            <RevenueBarGraph
              data={data?.daily_usage_revenue_period_1}
              isLoading={isLoading}
            />
          </div>
          <Divider />
          <div>
            <MetricBarGraph range={dateRange} />
          </div>
        </Col>
      </Row>
    </PageLayout>
  );
};

export default Dashboard;
