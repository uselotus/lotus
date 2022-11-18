// @ts-ignore
import React, { FC } from "react";
import { RightOutlined, LeftOutlined, DoubleLeftOutlined } from '@ant-design/icons';
import "./CustomPagination.css"

interface CustomPaginationProps {
    cursor:string,
    previous:string,
    next:string,
    currentPage:number,
    handleMovements:(value :"LEFT" | "RIGHT" | "START") => void
}


const CustomPagination: FC<CustomPaginationProps> = ({ cursor, currentPage, handleMovements, previous, next}) => (
        <div className="flex justify-center space-x-4">
        <button
            disabled={!cursor || currentPage == 1}
            className="movementButton"
            onClick={() => handleMovements("START")}
        >
            <DoubleLeftOutlined />
        </button>
        <button
            className="movementButton"
            disabled={ previous === "null"}
            onClick={() => handleMovements("LEFT")}
        >
            <LeftOutlined />
        </button>
        <div className="currentPageNumber"> {currentPage} </div>
        <button
            className="movementButton"
            disabled={next === "null"}
            onClick={() => handleMovements("RIGHT")}
        ><RightOutlined />
        </button>
    </div>
    );

export default CustomPagination;
