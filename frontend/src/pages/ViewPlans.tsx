// @ts-ignore
import React, { FC } from "react";
import {
  Button,
  Row,
  Col,
  Tabs,
} from "antd";
import { Plan } from "../api/api";
import {ArrowRightOutlined} from "@ant-design/icons";
import {Component, PlanType} from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import {FeatureType} from "../types/feature-type";
import PlanCard from "../components/Plans/PlanCard/PlanCard";

const ViewPlans: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  // const {
  //   data: plans,
  //   isLoading,
  //   isError,
  // }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(["plan_list"], () =>
  //   Plan.getPlans().then((res) => {
  //     return res;
  //   })
  // );

    const features: FeatureType[] = [
        {
            feature_name: "string",
            feature_description: "string",
        }
    ]

    const components: Component[] = [
        {
            free_metric_units: "string",
            cost_per_batch: "12",
            metric_units_per_batch:"12",
            max_metric_units:"12",
            id: 12,
            billable_metric: {
                event_name:"12",
                property_name:"12",
                aggregation_type:"12",
                metric_type:"12",
            }
        }
    ]

    const plans :PlanType[] = [
        {
            name: "40K Words",
            interval: "plan 1 interval",
            description: "plan 1 description",
            flat_rate: 20,
            currency: "string",
            id: 1,
            pay_in_advance: true,
            time_created: "string",
            billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
            active_subscriptions: 20,
            features: features,
            components:components

        },
        {
            name: "100K Words",
            interval: "plan 1 interval",
            description: "plan 1 description",
            flat_rate: 20,
            currency: "string",
            id: 1,
            pay_in_advance: true,
            time_created: "string",
            billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
            active_subscriptions: 20,
            features: features,
            components:components

        },
        {
            name: "Enterprise",
            interval: "plan 1 interval",
            description: "plan 1 description",
            flat_rate: 20,
            currency: "string",
            id: 1,
            pay_in_advance: true,
            time_created: "string",
            billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
            active_subscriptions: 20,
            features: features,
            components:components

        },
    ]

  const mutation = useMutation((post: string) => Plan.deletePlan(post), {
    onSuccess: () => {
      toast.success("Successfully deleted Plan");
      queryClient.invalidateQueries(["plan_list"]);
    },

    onError: (e) => {
      toast.error("Error deleting plan");
    },
  });

  const deletePlan = (version_id: string) => {
    mutation.mutate(version_id);
  };

  return (
    <PageLayout
      title="Plans"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          style={{ background: "black" }}
          className="text-white"
          size="large"
          key="create-plan"
        >
            <div className="flex items-center justify-between text-white">
                <div>Create new Plan</div>
                <ArrowRightOutlined className="pl-2" />
            </div>

        </Button>,
      ]}
    >
        <Tabs defaultActiveKey="1">
            <Tabs.TabPane tab="Monthly" key="1">
                <Row gutter={[0, 24]}>
                    {plans?.map((item, key) => (
                        <Col span={8} key={key}>
                            <PlanCard plan={item} deletePlan={deletePlan} />
                        </Col>
                    ))}
                </Row>
            </Tabs.TabPane>
            <Tabs.TabPane tab="Yearly" key="2">
                <Row gutter={[0, 24]}>
                    {plans?.map((item, key) => (
                        <Col span={8} key={key}>
                            <PlanCard plan={item} deletePlan={deletePlan} />
                        </Col>
                    ))}
                </Row>
            </Tabs.TabPane>
        </Tabs>
    </PageLayout>
  );
};

export default ViewPlans;
