import React, { FC, useEffect, useState } from "react";
import {
  Avatar,
  Divider,
  List,
  Skeleton,
  Button,
  Card,
  PageHeader,
  Row,
  Col,
} from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { Plan } from "../api/api";
import { PlanType } from "../types/plan-type";
import PlanDisplayBasic from "../components/PlanDisplayBasic";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";

const ViewPlans: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  const {
    data: plans,
    isLoading,
    isError,
  }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(["plan_list"], () =>
    Plan.getPlans().then((res) => {
      return res;
    })
  );

  const mutation = useMutation((post: string) => Plan.deletePlan(post), {
    onSuccess: () => {
      toast.success("Successfully deleted Plan");
      queryClient.invalidateQueries(["plan_list"]);
    },

    onError: (e) => {
      toast.error("Error deleting plan");
    },
  });

  const deletePlan = (billing_plan_id: string) => {
    mutation.mutate(billing_plan_id);
  };

  return (
    <PageLayout
      title="Plans"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          className="bg-black text-white justify-self-end"
          size="large"
          key={"create-plan"}
        >
          Create Plan
        </Button>,
      ]}
    >
      <Row gutter={[0, 24]}>
        {plans?.map((item, key) => (
          <Col span={24} key={key}>
            <PlanDisplayBasic plan={item} deletePlan={deletePlan} />
          </Col>
        ))}
      </Row>
    </PageLayout>
  );
};

export default ViewPlans;
